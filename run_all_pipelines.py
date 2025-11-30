import subprocess

scripts = [
    "pipelines/fed_plumbing.py",
    "pipelines/yield_curve.py",
    "pipelines/credit_spreads.py",
    "pipelines/fx_liquidity.py",
    "pipelines/macro_core.py"
]

print("\n🔄 Running all pipeline scripts...\n")

for script in scripts:
    print(f"▶ Running {script}...")
    result = subprocess.run(["python", script], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ {script} completed successfully.\n")
    else:
        print(f"❌ {script} failed:\n{result.stderr}\n")

print("✅ All pipelines finished.")
