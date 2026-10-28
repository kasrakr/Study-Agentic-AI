# Persian / فارسی user interface

The frontend supports English (default) and Persian without an additional i18n dependency. Use the language selector in the sidebar or mobile navigation. The selection is saved under `study-agent:locale` in browser localStorage, and changes the document's `lang` and `dir` attributes.

## Install the supplied Anjoman Bold font locally

The Anjoman Bold file provided for this feature contains a Fontiran copyright and an explicit licensing requirement. **Do not commit or redistribute the font with this public repository unless you have a license that authorizes redistribution.**

With a valid website/app usage license, place your own copy of the uploaded file at:

```
frontend/public/fonts/Anjoman-Bold.ttf
```

Create the directory if necessary. Keep that file untracked. During development Vite serves `/fonts/Anjoman-Bold.ttf`. The Persian theme uses the Anjoman family, with Tahoma/Arial fallback if the licensed font is absent. For better body-text readability consider obtaining a licensed regular weight too; this upload contains only the Bold face.

## Development and checks

```bash
cd frontend
npm ci
npm run typecheck
npm test
npm run build
```

The UI and accessibility labels are translated. User questions, uploaded text, citation excerpts, filenames, links, API fields, source markers, and technical commands are kept verbatim. The selected language does not change API request/response schemas. Persian starter prompts are sent in Persian, and the model is instructed to match the language of the student's question.

If a new UI label is added, add its Persian translation to `frontend/src/i18n.tsx` and render it using `tr("English label")` or `useTranslation().t("English label")`.
