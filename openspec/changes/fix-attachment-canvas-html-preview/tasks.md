## 1. Client attachment recognition

- [x] 1.1 Add extension-aware attachment filtering for drag and paste, including `.canvas` with empty or generic browser MIME values.
- [x] 1.2 Preserve canonical `.canvas` metadata through the existing upload helper and verify the attachment node receives the resolved type.
- [x] 1.3 Align the multipart file-part MIME with the signed upload policy for generic browser MIME values.

## 2. HTML attachment presentation

- [x] 2.1 Default Page HTML attachment previews to the isolated interactive iframe while retaining Download and fallback behavior.
- [x] 2.2 Default editor HTML attachment previews to the isolated interactive iframe while retaining View source, Download, and stop/failure controls.

## 3. Deployment and verification

- [x] 3.1 Deploy the affected web services with `scripts/test/deploy-test.ps1`.
- [x] 3.2 Have an independent Tester verify Canvas paste/drop upload and default HTML preview, including Download/source fallbacks and sandbox behavior.
