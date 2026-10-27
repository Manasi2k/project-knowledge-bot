from kb.config import load_nextcloud_settings
from kb.files import browse, find_files
from kb.nextcloud_client import NextcloudClient
from kb.sheets import aggregate

settings=load_nextcloud_settings()
client=NextcloudClient(settings)
base=settings.base_url


print("1. Architecture.pdf, any project:")
for e in find_files(client, "Architecture.pdf"):
    print("  ", e.path, f"{base}/f/{e.file_id}")

print("\n2. Architecture.pdf in Project_B:")
for e in find_files(client, "Architecture.pdf", "Project_B"):
    print("  ", e.path, f"{base}/f/{e.file_id}")

print("\n3. Partial name 'metrics':")
for e in find_files(client, "metrics"):
    print("  ", e.path)

print("\n4. Folder Projects/Project_C/Technical_Documents:")
for e in browse(client, "Projects/Project_C/Technical_Documents"):
    print("  ", "DIR " if e.is_dir else "FILE", e.name)

print("\n5. Q1 revenue per project (computed by pandas):")
for project in ("Project_A", "Project_B"):
    hits = find_files(client, "Project_Metrics.xlsx", project)
    if not hits:
        print("  ", project, "workbook not found")
        continue
    r = aggregate(client.download(hits[0].path), "Revenue", "Revenue_USD", "sum", {"Quarter": "Q1"})
    print(f"   {hits[0].path}\n     sheet '{r.sheet}', column {r.column}, rows {r.rows}: {r.value:,.0f}")