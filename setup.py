from __future__ import annotations

import email.message
import os
import platform
import runpy
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
VERSION_HELPERS = runpy.run_path(str(ROOT / "tools" / "version.py"))
ARCH_ALIASES = {
    "aarch64": "aarch64",
    "amd64": "x86_64",
    "arm64": "aarch64",
    "x86_64": "x86_64",
}


def package_version() -> str:
    return VERSION_HELPERS["package_version"]()


def glibc_version() -> str:
    override = os.environ.get("JAI_GLIBC_VERSION")
    if override:
        return override

    libc_name, version = platform.libc_ver()
    if libc_name == "glibc" and version:
        return version

    if "CS_GNU_LIBC_VERSION" in getattr(os, "confstr_names", {}):
        value = os.confstr("CS_GNU_LIBC_VERSION")
        if value and value.startswith("glibc "):
            return value.split()[1]

    raise RuntimeError("Unable to determine glibc version for wheel tag. Set JAI_GLIBC_VERSION.")


def wheel_arch() -> str:
    machine = platform.machine().lower()
    try:
        return ARCH_ALIASES[machine]
    except KeyError as exc:
        raise RuntimeError(
            f"Unsupported Linux architecture for wheel tag: {machine!r}. "
            "Set JAI_WHEEL_PLATFORM_TAG explicitly to override."
        ) from exc


def wheel_platform_tag() -> str:
    override = os.environ.get("JAI_WHEEL_PLATFORM_TAG")
    if override:
        return override

    major, minor, *_ = glibc_version().split(".")
    return f"manylinux_{major}_{minor}_{wheel_arch()}"


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
