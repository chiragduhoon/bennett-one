# BENNETT ONE — web app

React 19 + TypeScript + Vite + Tailwind. Talks to the FastAPI backend through the Vite proxy (`/api` → `localhost:8000`).

```bash
npm install
npm run dev      # http://localhost:5173
npm run lint
npm run build    # type-check + production bundle
```

| Path | What |
|---|---|
| `src/pages/Chat.tsx` | streaming chat, inline `[S1]` citation chips, source drawer, rule-engine verdict card |
| `src/pages/Eligibility.tsx` | eligibility checker form → `/api/eligibility` (deterministic rule engine) |
| `src/pages/Admin.tsx` | document versions, policy-conflict review, upload + approval, audit log |
| `src/lib/api.ts` | typed API client and Server-Sent-Events stream reader |

University logos and photos go in `public/brand/` (not committed). Without them the app still works; images are simply hidden.
