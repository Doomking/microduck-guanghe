"""Validate V302 with the exact control.102 payload and isolated maintenance modules."""
from pathlib import Path
import base64,hashlib,io,json,sys,tarfile,tempfile,types,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import firmware_packages
import maintenance_components as components
from controls import ControlError
from remote_input import Input

EXPECTED="d301e5e942eae36cb38e76729cdc97c1834ddacab23b10afea6d761b530ef20d"
class Robot:
    def __init__(self):self.calls=[]
    def request(self,method,params=None):
        self.calls.append((method,params))
        return {"bindings":[{"button":"a","skill":"ground_pick"},{"button":"x","skill":"roulade"},{"button":"rb","skill":"kick_right"},{"button":"dpad_down","skill":"sitstand"}]} if method=="pad.bindings" else {}
    def notify(self,calls):self.calls.extend(calls)
    def close(self):pass

class Tests(unittest.TestCase):
    def test_native_payload_is_unchanged_control102_with_eleven_models(self):
        raw=(ROOT/"updates"/firmware_packages.ARCHIVE_NAME).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),EXPECTED)
        info=firmware_packages.bundle_info()
        self.assertEqual(info["build"],"1fa843-feetech-ft6-control.102")
        self.assertEqual(set(info["models"]),{"walk","sitstand","ground_pick","roulade","kick_left","kick_right","play_dead"})
        with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as archive:
            members=archive.getmembers()
            self.assertEqual(sum(m.name.endswith(".onnx") for m in members),11)
            build=json.load(archive.extractfile("Microduck-Robotd-FT6-R17/BUILD.json"))
            self.assertEqual(build["build"],info["build"])
            self.assertEqual(build["models"],info["models"])

    def test_components_keep_v302_bytes_separate_from_native_firmware(self):
        bundle=components.component_bundle()
        self.assertEqual(set(bundle["files"]),set(components.FILES))
        for name,row in bundle["files"].items():
            self.assertEqual(base64.b64decode(row["data"]),(ROOT/name).read_bytes())
        self.assertEqual(bundle["component_id"],json.loads((ROOT/"BUILD_MANIFEST.json").read_text())["maintenance_component_id"])

    def test_corrupted_component_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/"updates").mkdir()
            (root/"BUILD_MANIFEST.json").write_bytes((ROOT/"BUILD_MANIFEST.json").read_bytes())
            data=(ROOT/"updates"/components.COMPONENT_ARCHIVE).read_bytes()
            (root/"updates"/components.COMPONENT_ARCHIVE).write_bytes(data+b"corruption")
            with patch.object(firmware_packages,"ROOT",root),patch.object(firmware_packages,"bundle_info",return_value={}):
                with self.assertRaises(ControlError):components.component_bundle()

    def test_prepare_only_creates_sidecar_and_preserves_native_files_models_and_calibration(self):
        bundle=components.component_bundle()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);install=root/"native";install.mkdir()
            for name in ("robotd","padd","gamesir-xboxd","robotd-profile.toml","calibration.json","policy.onnx"):
                (install/name).write_text("known-good-"+name)
            before={p.name:p.read_bytes() for p in install.iterdir()}
            remote=types.ModuleType("component_prepare_fixture")
            exec(compile(components.REMOTE_SOURCE,"component_prepare_fixture","exec"),remote.__dict__)
            remote.INSTALL=install;remote.COMPONENTS=install/"maintenance-components"
            remote.LOCK=root/"lock"
            remote.system_state=lambda:{"robotd_running":False}
            remote.lease_status=lambda token=None:{"active":False,"owned":False,"mode":"idle"}
            request={"action":"prepare","component_id":bundle["component_id"],
                     "hashes":{n:{"size":r["size"],"sha256":r["sha256"]} for n,r in bundle["files"].items()},
                     "files":{n:r["data"] for n,r in bundle["files"].items()}}
            result=remote.execute(request)
            self.assertTrue(result["prepared"])
            for name,data in before.items():self.assertEqual((install/name).read_bytes(),data)
            target=Path(result["worker_path"]).parent
            self.assertEqual(target.parent,install/"maintenance-components")
            self.assertEqual({p.name for p in target.iterdir()},set(components.FILES)|{"component-manifest.json"})
            again=remote.execute(request)
            self.assertFalse(again["prepared"])

    def test_web_buttons_use_existing_native_bindings(self):
        robot=Robot();control=Input(robot,clock=lambda:0)
        control.drive_reader=lambda:{"supported":False,"speed":.3}
        axes={key:0 for key in ("lx","ly","rx","ry","lt","rt","dx","dy")}
        owner="baseline-input-owner"
        send=lambda buttons,dx=0,dy=0:control.command({"action":"state","owner":owner,"frame":{"axes":dict(axes,dx=dx,dy=dy),"buttons":buttons}})
        send(["b"],dx=-1);send([])
        self.assertFalse(any(m=="robot.do" for m,p in robot.calls))
        send(["a"]);send([]);send(["x"]);send([]);send(["rb"]);send([]);send([],dy=1)
        self.assertEqual([p["skill"] for m,p in robot.calls if m=="robot.do"],["ground_pick","roulade","kick_right","sitstand"])
        self.assertEqual(control.mode,"drive")

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    Path(__file__).with_name("console102-results.json").write_text(json.dumps({"passed":result.wasSuccessful(),"tests":result.testsRun,"native_firmware_sha256":EXPECTED,"hardware_tested":False,"scope":"exact control102 payload, separate maintenance sidecar, legacy web input"},indent=2)+"\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)

