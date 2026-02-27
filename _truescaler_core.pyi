from typing import Any, Dict

def process_file_cpp(
    path: str,
    out_dir: str = "",
    out_name: str = "",
    threshold: int = 245,
    tolerance: int = 0,
    require_square: bool = False,
    max_checks: int = 10000,
    write_downsample: bool = True,
    verbose: bool = True,
    out_format: str = "png",
) -> Dict[str, Any]: ...
