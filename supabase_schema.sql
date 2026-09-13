-- S.D. Public School Sports Department - Supabase schema
create table if not exists public.users (id bigserial primary key, user_id text unique not null, password_hash text not null, role text not null, active integer default 1, created_at text);
create table if not exists public.teachers (id bigserial primary key, user_id bigint unique references public.users(id) on delete cascade, name text, designation text, house text, photo text, mobile text, email text, qualification text, joining_date text, class_name text, section text, roll_no text, guardian text, remarks text);
create table if not exists public.students (id bigserial primary key, user_id bigint unique references public.users(id) on delete set null, admission_no text unique, name text, class_name text, section text, roll_no text, house text, house_position text, blood_group text, dob text, photo text, height double precision, weight double precision, bmi double precision, body_age text, guardian text, phone text, address text, remarks text, active integer default 1);
create table if not exists public.events (id bigserial primary key, name text, category text, game text, event_date text, house1 text, house2 text, venue text, description text);
create table if not exists public.results (id bigserial primary key, event_id bigint references public.events(id) on delete cascade, house text, position text, points double precision, remarks text);
create table if not exists public.participation (id bigserial primary key, event_id bigint references public.events(id) on delete cascade, student_id bigint references public.students(id) on delete cascade, performance text, position text, remarks text);
create table if not exists public.assessments (id bigserial primary key, student_id bigint references public.students(id) on delete cascade, assess_date text, fitness text, running text, strength text, flexibility text, endurance text, discipline text, participation text, remarks text);
create table if not exists public.annual (id bigserial primary key, name text, category text, event_date text, house text, position text, points double precision, remarks text);
create table if not exists public.certificates (id bigserial primary key, student_id bigint references public.students(id) on delete cascade, event_name text, game text, position text, certificate_date text, remarks text);
create table if not exists public.gallery (id bigserial primary key, filename text, caption text, house text, event_name text, uploaded_by text, created_at text);
create table if not exists public.reset_requests (id bigserial primary key, user_id text, requested_at text, status text default 'pending');
create table if not exists public.audit (id bigserial primary key, user_id text, action text, created_at text);
create table if not exists public.settings (k text primary key, v text);
create table if not exists public.houses (id bigserial primary key, name text unique not null, logo text, active integer default 1);
create table if not exists public.house_positions (id bigserial primary key, name text unique not null, description text, active integer default 1);
create table if not exists public.games (id bigserial primary key, name text unique not null, active integer default 1);

insert into public.settings(k,v) values
('school_name','S.D. Public School'),('school_address','Kumhrar, Patna-07'),('department','SPORTS DEPARTMENT'),('principal_name',''),('sports_teacher_name',''),('school_logo',''),
('house_1','Aryabhatta House'),('house_2','Ashoka House'),('house_3','Gautam House'),('house_4','Chanakya House'),('house_logo_1',''),('house_logo_2',''),('house_logo_3',''),('house_logo_4','')
on conflict(k) do nothing;
insert into public.houses(name) values ('Aryabhatta House'),('Ashoka House'),('Gautam House'),('Chanakya House') on conflict(name) do nothing;
insert into public.house_positions(name) values ('House Captain'),('Vice Captain'),('Prefect'),('House Member') on conflict(name) do nothing;
insert into public.games(name) values ('Athletics'),('Football'),('Cricket'),('Basketball'),('Volleyball'),('Badminton'),('Table Tennis'),('Tennis'),('Kho-Kho'),('Kabaddi'),('Chess'),('Carrom'),('Handball'),('Hockey'),('Throwball'),('Long Jump'),('High Jump'),('Shot Put'),('Discus Throw'),('Javelin Throw'),('100m'),('200m'),('400m'),('800m'),('1500m'),('Relay'),('Yoga'),('Skipping') on conflict(name) do nothing;

alter table public.students add column if not exists house_position text;
alter table public.teachers add column if not exists mobile text;
alter table public.teachers add column if not exists email text;
alter table public.teachers add column if not exists qualification text;
alter table public.teachers add column if not exists joining_date text;
alter table public.teachers add column if not exists class_name text;
alter table public.teachers add column if not exists section text;
alter table public.teachers add column if not exists roll_no text;
alter table public.teachers add column if not exists guardian text;
alter table public.teachers add column if not exists remarks text;

create index if not exists idx_students_house on public.students(house);
create index if not exists idx_students_name on public.students(name);
create index if not exists idx_teachers_house on public.teachers(house);
create index if not exists idx_events_date on public.events(event_date);
create index if not exists idx_results_house on public.results(house);
create index if not exists idx_participation_student on public.participation(student_id);
create index if not exists idx_assessments_student on public.assessments(student_id);
create index if not exists idx_annual_house on public.annual(house);
create index if not exists idx_gallery_house on public.gallery(house);

-- RLS is intentionally enabled. The application uses a server-side Postgres connection
-- and server-side Supabase service role for Storage; no secret key is exposed to browsers.
alter table public.users enable row level security;
alter table public.teachers enable row level security;
alter table public.students enable row level security;
alter table public.events enable row level security;
alter table public.results enable row level security;
alter table public.participation enable row level security;
alter table public.assessments enable row level security;
alter table public.annual enable row level security;
alter table public.certificates enable row level security;
alter table public.gallery enable row level security;
alter table public.reset_requests enable row level security;
alter table public.audit enable row level security;
alter table public.settings enable row level security;
alter table public.houses enable row level security;
alter table public.house_positions enable row level security;
alter table public.games enable row level security;
