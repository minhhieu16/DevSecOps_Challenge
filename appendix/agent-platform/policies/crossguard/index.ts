// Purpose: Papaya CrossGuard policy pack. All policies are `mandatory` (block preview/up).
// Controls: DET-011 naming/tag convention; S3 public access + SSE-KMS; no secrets in env vars;
//   Secrets Manager CMK + tags; nonprod IAM permission boundary (DET-002 preventive twin);
//   no IAM "*":"*"; RDS encryption. See README.md for the control mapping.
// Assumption: Pulumi stack name == environment (`nonprod` | `prod`). Stack is parsed from the URN.
// Verify: type names/props against the pinned @pulumi/aws version; stack-level S3 checks rely on
//   PolicyResource.propertyDependencies (see README "Verify").
import * as aws from "@pulumi/aws";
import {
    PolicyPack,
    ResourceValidationArgs,
    ReportViolation,
    StackValidationArgs,
    validateResourceOfType,
    validateStackResourcesOfType,
} from "@pulumi/policy";

const REQUIRED_TAGS = ["env", "service", "owner", "data-class"] as const;
const DATA_CLASSES = ["phi", "pii", "internal", "public"];
const SECRET_KEY_RE = /SECRET|TOKEN|PASSWORD|API_KEY/i;
const ARN_RE = /^arn:aws[a-z-]*:/;
const NONPROD_BOUNDARY = "nonprod-boundary";

/** urn:pulumi:<stack>::<project>::<type>::<name> -> stack name (== env). */
function envFromUrn(urn: string): string {
    const first = urn.split("::")[0]; // urn:pulumi:prod
    return first.substring(first.lastIndexOf(":") + 1);
}

/** Naming: physical name must be set explicitly and start with `<env>-`. */
function checkName(env: string, name: string | undefined, report: ReportViolation, prefix = `${env}-`) {
    if (!name) {
        report(`Set an explicit physical name starting with '${prefix}' (<env>-<service>-<name>); auto-names are not allowed.`);
    } else if (!name.startsWith(prefix)) {
        report(`Name '${name}' must start with '${prefix}' (stack env '${env}').`);
    }
}

/** Required tags present, env tag matches the stack, data-class valid. */
function checkTags(env: string, tags: Record<string, string> | undefined, report: ReportViolation) {
    const t = tags ?? {};
    for (const k of REQUIRED_TAGS) {
        if (!t[k]) report(`Missing required tag '${k}' (required: ${REQUIRED_TAGS.join(", ")}).`);
    }
    if (t["env"] && t["env"] !== env) report(`Tag env='${t["env"]}' does not match stack env '${env}'.`);
    if (t["data-class"] && !DATA_CLASSES.includes(t["data-class"])) {
        report(`Tag data-class='${t["data-class"]}' must be one of ${DATA_CLASSES.join("|")}.`);
    }
}

/** Parse an IAM policy document that may be a JSON string or an already-object value. */
function parsePolicy(doc: unknown): any | undefined {
    if (!doc) return undefined;
    if (typeof doc === "string") {
        try { return JSON.parse(doc); } catch { return undefined; }
    }
    return doc;
}

function asArray<T>(v: T | T[] | undefined): T[] {
    return v === undefined ? [] : Array.isArray(v) ? v : [v];
}

/** True if an Allow statement grants Action "*" (or "*:*") on Resource "*". */
function hasAllowStarStar(doc: unknown): boolean {
    const p = parsePolicy(doc);
    if (!p) return false;
    return asArray<any>(p.Statement ?? p.statement).some((s) => {
        const effect = s.Effect ?? s.effect;
        if (effect !== "Allow") return false;
        const actions = asArray<string>(s.Action ?? s.action);
        const resources = asArray<string>(s.Resource ?? s.resource);
        return actions.some((a) => a === "*" || a === "*:*") && resources.some((r) => r === "*");
    });
}

function envVarViolations(vars: Record<string, string> | undefined, report: ReportViolation) {
    for (const [k, v] of Object.entries(vars ?? {})) {
        if (SECRET_KEY_RE.test(k) && !ARN_RE.test(String(v))) {
            report(`Environment variable '${k}' looks like a secret; reference a Secrets Manager/SSM ARN instead of a value.`);
        }
    }
}

const mandatory = "mandatory" as const;

new PolicyPack("papaya-mandatory", {
    policies: [
        // ---- Naming + tags (DET-011) -------------------------------------------------------
        {
            name: "naming-prefix-s3",
            description: "S3 buckets must be named papaya-<env>-<service>-<name>.",
            enforcementLevel: mandatory,
            validateResource: [aws.s3.Bucket, aws.s3.BucketV2].map((t) =>
                validateResourceOfType(t as any, (b: any, args: ResourceValidationArgs, report: ReportViolation) => {
                    const env = envFromUrn(args.urn);
                    checkName(env, b.bucket, report, `papaya-${env}-`);
                }),
            ),
        },
        {
            name: "naming-prefix-resources",
            description: "Lambda, IAM role, secret and RDS cluster physical names must start with <env>-.",
            enforcementLevel: mandatory,
            validateResource: [
                validateResourceOfType(aws.lambda.Function, (r, args, report) => checkName(envFromUrn(args.urn), r.name, report)),
                validateResourceOfType(aws.iam.Role, (r, args, report) => checkName(envFromUrn(args.urn), r.name, report)),
                validateResourceOfType(aws.secretsmanager.Secret, (r, args, report) => checkName(envFromUrn(args.urn), r.name, report)),
                validateResourceOfType(aws.rds.Cluster, (r, args, report) => checkName(envFromUrn(args.urn), r.clusterIdentifier, report)),
            ],
        },
        {
            name: "required-tags",
            description: "Taggable resources must carry env, service, owner, data-class (env must equal the stack).",
            enforcementLevel: mandatory,
            validateResource: [
                ...[aws.s3.Bucket, aws.s3.BucketV2].map((t) =>
                    validateResourceOfType(t as any, (r: any, args: ResourceValidationArgs, report: ReportViolation) =>
                        checkTags(envFromUrn(args.urn), r.tags, report)),
                ),
                validateResourceOfType(aws.lambda.Function, (r, args, report) => checkTags(envFromUrn(args.urn), r.tags, report)),
                validateResourceOfType(aws.iam.Role, (r, args, report) => checkTags(envFromUrn(args.urn), r.tags, report)),
                validateResourceOfType(aws.secretsmanager.Secret, (r, args, report) => checkTags(envFromUrn(args.urn), r.tags, report)),
                validateResourceOfType(aws.rds.Cluster, (r, args, report) => checkTags(envFromUrn(args.urn), r.tags, report)),
            ],
        },

        // ---- S3: public access block + SSE-KMS (stack-level: companion resources) ----------
        {
            name: "s3-block-public-access-and-sse-kms",
            description: "Every S3 bucket must have a BucketPublicAccessBlock (all four flags true) and SSE-KMS (aws:kms) configuration.",
            enforcementLevel: mandatory,
            validateStack: (args: StackValidationArgs, report: ReportViolation) => {
                const buckets = args.resources.filter((r) => r.isType(aws.s3.Bucket) || r.isType(aws.s3.BucketV2));
                const pabs = args.resources.filter((r) => r.isType(aws.s3.BucketPublicAccessBlock));
                const sseV2 = args.resources.filter((r) => r.isType(aws.s3.BucketServerSideEncryptionConfigurationV2));
                const dependsOn = (companion: any, bucketUrn: string) =>
                    (companion.propertyDependencies?.["bucket"] ?? []).some((d: any) => d.urn === bucketUrn) ||
                    (companion.dependencies ?? []).some((d: any) => d.urn === bucketUrn);
                for (const b of buckets) {
                    const pab = pabs.find((p) => dependsOn(p, b.urn));
                    const pp: any = pab?.props ?? {};
                    if (!pab || !(pp.blockPublicAcls && pp.blockPublicPolicy && pp.ignorePublicAcls && pp.restrictPublicBuckets)) {
                        report(`Bucket ${b.name}: add aws.s3.BucketPublicAccessBlock with all four flags true.`);
                    }
                    const inline: any = (b.props as any).serverSideEncryptionConfiguration;
                    const inlineOk = JSON.stringify(inline ?? {}).includes("aws:kms");
                    const sse = sseV2.find((s) => dependsOn(s, b.urn));
                    const sseOk = !!sse && JSON.stringify((sse.props as any).rules ?? {}).includes("aws:kms");
                    if (!inlineOk && !sseOk) {
                        report(`Bucket ${b.name}: SSE-KMS required (sseAlgorithm 'aws:kms' with a CMK, e.g. alias/<env>-<service>-data).`);
                    }
                }
            },
        },

        // ---- No secrets in env vars ---------------------------------------------------------
        {
            name: "no-secret-env-vars",
            description: "Lambda/ECS environment variables named like SECRET/TOKEN/PASSWORD/API_KEY must hold an ARN reference, not a value.",
            enforcementLevel: mandatory,
            validateResource: [
                validateResourceOfType(aws.lambda.Function, (fn, _args, report) => envVarViolations(fn.environment?.variables, report)),
                validateResourceOfType(aws.ecs.TaskDefinition, (td, _args, report) => {
                    const defs = parsePolicy(td.containerDefinitions);
                    for (const c of asArray<any>(defs)) {
                        const vars: Record<string, string> = {};
                        for (const e of asArray<any>(c.environment)) vars[e.name] = e.value;
                        envVarViolations(vars, report);
                    }
                }),
            ],
        },

        // ---- Secrets Manager ----------------------------------------------------------------
        {
            name: "secretsmanager-cmk-and-tags",
            description: "Every aws.secretsmanager.Secret must set kmsKeyId (CMK) and required tags (owner tag drives prod-secret-intake ABAC).",
            enforcementLevel: mandatory,
            validateResource: validateResourceOfType(aws.secretsmanager.Secret, (s, args, report) => {
                if (!s.kmsKeyId) report("Secret must set kmsKeyId (e.g. alias/<env>-secrets), not the default AWS-managed key.");
                checkTags(envFromUrn(args.urn), s.tags, report);
            }),
        },

        // ---- IAM ----------------------------------------------------------------------------
        {
            name: "nonprod-iam-role-permissions-boundary",
            description: "In the nonprod stack every IAM role must set permissionsBoundary = nonprod-boundary and be named nonprod-*.",
            enforcementLevel: mandatory,
            validateResource: validateResourceOfType(aws.iam.Role, (r, args, report) => {
                if (envFromUrn(args.urn) !== "nonprod") return;
                const pb = r.permissionsBoundary as string | undefined;
                if (!pb || !(pb === NONPROD_BOUNDARY || pb.endsWith(`:policy/${NONPROD_BOUNDARY}`))) {
                    report(`Role must set permissionsBoundary to ${NONPROD_BOUNDARY}.`);
                }
            }),
        },
        {
            name: "no-iam-allow-star-star",
            description: "No IAM policy may Allow Action '*' on Resource '*'.",
            enforcementLevel: mandatory,
            validateResource: [
                validateResourceOfType(aws.iam.Policy, (p, _a, report) => {
                    if (hasAllowStarStar(p.policy)) report("Managed policy allows Action '*' on Resource '*'.");
                }),
                validateResourceOfType(aws.iam.RolePolicy, (p, _a, report) => {
                    if (hasAllowStarStar(p.policy)) report("Inline role policy allows Action '*' on Resource '*'.");
                }),
                validateResourceOfType(aws.iam.Role, (r, _a, report) => {
                    for (const ip of r.inlinePolicies ?? []) {
                        if (hasAllowStarStar(ip.policy)) report(`Inline policy '${ip.name}' allows Action '*' on Resource '*'.`);
                    }
                }),
            ],
        },

        // ---- RDS ----------------------------------------------------------------------------
        {
            name: "rds-storage-encrypted",
            description: "RDS/Aurora storage must be encrypted (storageEncrypted = true, CMK preferred).",
            enforcementLevel: mandatory,
            validateResource: [
                validateResourceOfType(aws.rds.Cluster, (c, _a, report) => {
                    if (c.storageEncrypted !== true) report("rds.Cluster must set storageEncrypted = true.");
                }),
                validateResourceOfType(aws.rds.Instance, (i, _a, report) => {
                    if (i.storageEncrypted !== true) report("rds.Instance must set storageEncrypted = true.");
                }),
            ],
        },
    ],
});
