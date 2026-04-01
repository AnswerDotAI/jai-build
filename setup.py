from __future__ import annotations

import email.message
import os
import shutil
import tempfile
from pathlib import Path

from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.bdist_wheel import safe_version, safer_name
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).resolve().parent
PACKAGE_NAME = "jai-sandbox"
SUMMARY = "Linux sandbox for untrusted code execution"


def package_version() -> str:
    ns: dict[str, str] = {}
    exec((ROOT / "src/jai_sandbox/__init__.py").read_text(encoding="utf-8"), ns)
    return ns["__version__"]


def wheel_platform_tag() -> str:
    return "manylinux_2_39_x86_64"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class bdist_wheel(_bdist_wheel):
    def finalize_options(self) -> None:
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self) -> tuple[str, str, str]:
        return "py3", "none", wheel_platform_tag()

    def run(self) -> None:
        binary = ROOT / "jai_binary" / "jai"
        if not binary.exists():
            raise FileNotFoundError(f"Pre-built binary not found at {binary}. Run build.sh first.")

        self.mkpath(self.dist_dir)

        name = safer_name(PACKAGE_NAME)
        version = safe_version(package_version())
        impl_tag, abi_tag, plat_tag = self.get_tag()
        dist_info = f"{name}-{version}.dist-info"
        data_scripts = f"{name}-{version}.data/scripts"
        wheel_name = f"{name}-{version}-{impl_tag}-{abi_tag}-{plat_tag}.whl"
        wheel_path = Path(self.dist_dir) / wheel_name

        metadata = email.message.Message()
        metadata["Metadata-Version"] = "2.1"
        metadata["Name"] = PACKAGE_NAME
        metadata["Version"] = package_version()
        metadata["Summary"] = SUMMARY
        metadata["Requires-Python"] = ">=3.9"
        metadata["Description-Content-Type"] = "text/markdown"
        readme = ROOT / "README.md"
        if readme.exists(): metadata.set_payload(readme.read_text(encoding="utf-8"))

        wheel_text = (
            "Wheel-Version: 1.0\n"
            "Generator: jai-sandbox custom bdist_wheel\n"
            "Root-Is-Purelib: false\n"
            f"Tag: {impl_tag}-{abi_tag}-{plat_tag}\n"
        )

        with tempfile.TemporaryDirectory(prefix="jai-wheel.") as td:
            tree = Path(td)
            write_text(tree / "jai_sandbox" / "__init__.py",
                       (ROOT / "src/jai_sandbox/__init__.py").read_text(encoding="utf-8"))
            script_path = tree / data_scripts / "jai"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(binary, script_path)
            os.chmod(script_path, 0o755)
            write_text(tree / dist_info / "METADATA", metadata.as_string())
            write_text(tree / dist_info / "WHEEL", wheel_text)
            write_text(tree / dist_info / "top_level.txt", "jai_sandbox\n")

            with WheelFile(str(wheel_path), "w") as whl:
                whl.write_files(str(tree))

        self.distribution.dist_files.append(("bdist_wheel", "", str(wheel_path)))


setup(
    name=PACKAGE_NAME,
    version=package_version(),
    description=SUMMARY,
    packages=["jai_sandbox"],
    package_dir={"": "src"},
    python_requires=">=3.9",
    cmdclass={"bdist_wheel": bdist_wheel},
)
