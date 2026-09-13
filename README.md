# S.D. Public School — Sports Department
## GitHub + Netlify + Supabase final package

Deploy: GitHub -> Netlify -> Netlify Python Function -> Supabase Postgres + Supabase Storage.

Credentials: Owner `owner` / `ChangeMe123!`; Sports Teacher Co-Owner `SDPSEPT` / `sdpsept`. Change passwords after first login.

Permissions: Owner and Sports Teacher have full control. House Teacher is restricted to assigned House for Student Add/Remove/Photo. Prefect is NOT house-restricted and can work across all four Houses for Student Add/Remove/Photo. Student can only view My Report Card. Student, Teacher and Prefect profiles include House. Four House Logos are supported.

Supabase: run `supabase_schema.sql`; create a public Storage bucket named `sports-uploads`; set Netlify environment variables `SECRET_KEY`, `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET`. Never expose the service-role key in frontend code.

Modules: login/RBAC, students, BMI, assessments, events, house-based results, individual participation, annual sports, scoreboard, certificates, gallery, teachers/prefects, password change/reset request, settings, CSV export, backup, audit, CSRF and image validation.
