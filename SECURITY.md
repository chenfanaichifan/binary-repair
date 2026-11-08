# Security policy

## Scope

This repository is a research/MVP delivery, not a production service. It must not
be used to process client binaries or confidential material without explicit
authorization.

The host is not allowed to execute uploaded or repaired binaries. Execution,
compilation and symbolic analysis belong to the disposable guest under the
broker. Reports that require executing a binary on the host are out of scope.

## Reporting a vulnerability

Please report security issues privately through GitHub's **Security advisories**
for this repository. Do not open a public issue containing a vulnerability,
credential, client binary, private log or exploit detail.

Include:

- affected commit or release;
- reproduction steps;
- expected vs observed behavior;
- whether any secret or client material could be exposed.

## Secrets and client material

Never commit:

```text
.env files or API keys
private keys or tokens
client binaries
private host paths or logs
credentials for the broker/guest
```

The example environment file contains placeholders only.

## Accepted limitations

The project's known limitations are documented in
[`docs/acceptance/LIMITATIONS.md`](docs/acceptance/LIMITATIONS.md). V4 is a
model-level claim, not a binary-level proof; M4/Lead are the same operator; and
Review 9–12 original text is not recovered. Those are recorded limitations, not
hidden security guarantees.
