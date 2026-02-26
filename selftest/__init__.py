
# PACKAGED_ZIP_CONTENT_AUDIT
def test_packaged_zip_contains_local_packages():
    import subprocess, sys, zipfile
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    subprocess.run([sys.executable, "-m", "tools.package_beta"], cwd=root, check=True)
    dist = root / "dist"
    zips = sorted(dist.glob("Modulo_Beta_*.zip"), key=lambda p:p.stat().st_mtime)
    assert zips, "no beta zip produced"
    zpath = zips[-1]
    locals_ = []
    for p in root.iterdir():
        if p.is_dir() and (p / "__init__.py").exists() and p.name not in ("dist","__pycache__"):
            locals_.append(p.name)
    with zipfile.ZipFile(zpath) as z:
        namelist = set(z.namelist())
    missing=[]
    for name in locals_:
        if f"{name}/__init__.py" not in namelist:
            missing.append(name)
    assert not missing, "packaged zip missing local packages: " + ", ".join(missing)

