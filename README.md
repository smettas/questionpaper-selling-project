# QuestionPaper Selling Project

Local Django trial for NEET Physics, Chemistry and Biology. Class 11 and 12
appear as chapter groups. There is no separate class selection. Add sections
for multiple chapters or subjects. Questions are stored separately from the
existing OJAS app.

## Start on Windows

Install Python 3.11 or newer. Open Command Prompt in the project folder
and run `SETUP.cmd`. Open http://127.0.0.1:8000/. The server binds only to
the local computer. Run other commands in a second Command Prompt.

## Import your 100 questions

Place two selectable-text PDFs in the project folder: `questions.pdf` with
questions 1–100 and `answers.pdf` with matching numbered options. Start
with one chapter and tag the set using one subtopic and difficulty. You
can edit individual tags later in Django admin, or import smaller groups
with separate metadata. Example for a mixed Gravitation set:

```cmd
cd /d "E:\QuestionPaper Selling Project"
.venv\Scripts\python.exe manage.py import_paper questions.pdf answers.pdf --count 100 --subject physics --level 11 --chapter "Gravitation" --subtopic "Mixed practice" --difficulty moderate --publish
```

`--publish` activates questions whose four option labels are found in the
PDF text. Any flagged question remains inactive for review. Omit the flag
if you want every new question to start inactive. Reimporting identical
artwork skips it. Import a separate PDF batch for a different chapter or
difficulty. The supplied chapter/subtopic catalog is an editable starter.

Use `.venv\Scripts\python.exe manage.py createsuperuser` to manage the bank at
http://127.0.0.1:8000/admin/. The paper builder itself requires no account.
Add your branding, set the quantity, and download one ZIP containing the
question paper and matching answer key PDFs. Limit: 300 questions per paper.

## Storage and GitHub

The trial uses local SQLite and the local `media` directory by default.
For a separate private R2 bucket or a scoped bucket credential, set
`R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID` and
`R2_SECRET_ACCESS_KEY` in the Command Prompt before starting or importing.
R2 assets use the `question-paper-selling/` prefix. Choose storage before
importing. Switching the settings does not copy existing local assets.
The R2 integration was not tested against a live bucket.

To start version control, run `git init` inside this project. Create a new
private GitHub repository and use its URL as this project's origin.
Database, uploaded assets, virtual environment and environment files are
excluded from Git. Keep the login-free trial on localhost until customer
access is implemented.

## Deploy the web builder

1. Push this directory to a new private GitHub repository. In Railway,
   create a project for the builder, add PostgreSQL, and deploy a web
   service from that repository. The deploy settings are in railway.json.
2. On the web service, set DATABASE_URL to the PostgreSQL service variable
   reference (for example, ${{Postgres.DATABASE_URL}} if the service is named
   Postgres). Add DJANGO_SECRET_KEY with a freshly generated secret.
3. Set R2_BUCKET_NAME, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, and
   R2_SECRET_ACCESS_KEY as Railway variables. Use a private bucket.
   The token needs object read/write access to that bucket. A fresh bucket
   is recommended for separation. Existing credentials work if they cover
   the chosen bucket. No credentials belong in Git.
4. Generate a public domain from the Railway web service settings and
   deploy. The builder is accessible to anyone with the URL. Django admin
   and the PDF upload page require authentication.
5. Use railway ssh to enter the deployed web service, then run
   python manage.py check_storage and python manage.py createsuperuser.
6. Open /admin/import-questions/ on the deployed domain. Upload the question
   and answer PDFs, enter their question count and metadata, and select
   activation if the set is ready. Visit / to generate a paper.

The deployed database starts with the chapter catalog. Existing local
questions require a separate import or migration. The CLI importer and web
upload both use the configured storage. PDFs are rendered on the server.
