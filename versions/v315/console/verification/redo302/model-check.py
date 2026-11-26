"""Validate every bundled model with the actual ARM64 daemon (QEMU, no motors).

Arguments: firmware-directory robotd-binary qemu-binary arm64-sysroot.
"""
import concurrent.futures, json, pathlib, subprocess, sys
fw, daemon, qemu, sysroot = map(lambda v:pathlib.Path(v).resolve(),sys.argv[1:])
def check(p):
    run=subprocess.run([str(qemu),'-L',str(sysroot),'-E',f'LD_LIBRARY_PATH={sysroot}/lib/aarch64-linux-gnu:{sysroot}/usr/lib/aarch64-linux-gnu',
        '-E',f'ORT_DYLIB_PATH={fw}/onnxruntime/libonnxruntime.so.1.28.0',str(daemon),'validate-policy',str(p)],capture_output=True,text=True,timeout=120)
    return {'model':str(p.relative_to(fw)),'passed':run.returncode==0,'exit_code':run.returncode,'stdout':run.stdout.strip(),
        **({'error':run.stderr[-1800:]} if run.returncode else {})}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    rows=list(pool.map(check,sorted(fw.rglob('policy.onnx'))))
out=pathlib.Path(__file__).with_name('native-model-results.json')
out.write_text(json.dumps({'passed':all(r['passed'] for r in rows),'count':len(rows),'runtime':'actual ARM64 robotd + bundled ORT through QEMU; no hardware', 'models':rows},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':all(r['passed'] for r in rows),'models':len(rows),'failures':[r for r in rows if not r['passed']]},ensure_ascii=False))
sys.exit(0 if all(r['passed'] for r in rows) else 1)
