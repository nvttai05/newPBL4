run:
\tuvicorn sandbox.api:app --reload --port 8000 --app-dir src
test:
\tpytest -q
fmt:
\tblack src
