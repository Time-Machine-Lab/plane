## Independent test-environment verification

- Tester: fresh independent Tester sub-agent (`/root/canvas_html_tester`)
- Environment: deployed `web` service at `http://localhost:8000`
- Deployment: `20260902-001258-3ee7954ed9d1`
- Automated test suites: not run; repository guidance does not require them by default.

### Canvas upload and preview

- Uploaded `AI-TEST-canvas-upload.canvas` through the attachment picker.
- Upload succeeded and the new attachment displayed `application/json (1 KB)`.
- Canvas preview rendered with zoom controls; zoom interaction reached 125%.
- Download link was present and pointed to the authorized asset download endpoint.
- After a page refresh, the attachment still displayed `application/json (1 KB)`, confirming persisted canonical MIME metadata.

Evidence:

- `.runtime/test/AI-TEST-canvas-recheck-pass.png`
- `.runtime/test/AI-TEST-canvas-persisted.png`

### HTML adjacent regression

- HTML attachment rendered an iframe by default without an Open action.
- Script interaction inside the iframe succeeded.
- Download, View source, and Stop controls remained available.
- The iframe sandbox was exactly `allow-scripts`; `allow-same-origin` was absent.

Evidence:

- `.runtime/test/AI-TEST-canvas-html-final.png`

## Production follow-up diagnosis

- After the storage profile was activated, a fresh production Canvas upload still failed while the card correctly displayed `application/json`.
- The signed POST policy uses `application/json`, but the browser's original `.canvas` `File` can retain `application/octet-stream` as its multipart part MIME. The shared upload helper now uses the signed `Content-Type` when building that part.
- A fresh deployment and independent production recheck are required for this follow-up fix.
