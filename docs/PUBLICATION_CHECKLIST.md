# Publication checklist

Before publishing any extension to this repository:

- Use fictional names, identifiers and records.
- Keep credentials, environment files and private keys out of content and Git history.
- Exclude internal hosts, connection strings, infrastructure paths and source schemas.
- Exclude customer names, personal information, screenshots and captured operational traces.
- Scan both working files and all objects reachable from the commit being pushed.
- Review commit author metadata and remote URLs for unintended disclosures.
- Check diagrams and examples for operational details copied from an internal deployment.
- Clearly distinguish proposed behavior from implemented behavior.
- Credit referenced research without claiming a reproduction or novel contribution.
- Use a separate sanitized repository rather than pushing a private project's history.

The repository's offline explorer uses hard-coded fictional scenarios and no external network requests. It is an educational illustration, not a live execution trace.

Passing an automated scan does not prove an artifact contains no sensitive information. A final content review is still required.
