#pragma once

#include <string>

namespace truescaler {

struct ProcessResult {
    int scale_x;
    int scale_y;
    int true_w;
    int true_h;
    std::string out;
};

ProcessResult process_file_cpp(
    const std::string &path,
    const std::string &out_dir,
    const std::string &out_name,
    int threshold,
    int tolerance,
    bool require_square,
    int max_checks,
    bool write_downsample,
    bool verbose,
    const std::string &out_format
);

}  // namespace truescaler
