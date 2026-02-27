#include "core.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>

#include <pybind11/pybind11.h>

namespace py = pybind11;
namespace fs = std::filesystem;

namespace truescaler {

namespace {

std::vector<int> divisors(int n) {
    std::vector<int> d;
    for (int i = 1; i * i <= n; ++i) {
        if (n % i == 0) {
            d.push_back(i);
            if (i != n / i) d.push_back(n / i);
        }
    }
    std::sort(d.begin(), d.end());
    return d;
}

cv::Mat crop_whitespace(const cv::Mat &arr, int threshold) {
    const int h = arr.rows;
    const int w = arr.cols;
    int rmin = h, rmax = -1, cmin = w, cmax = -1;

    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            const cv::Vec3b px = arr.at<cv::Vec3b>(y, x);
            if (px[0] < threshold || px[1] < threshold || px[2] < threshold) {
                rmin = std::min(rmin, y);
                rmax = std::max(rmax, y);
                cmin = std::min(cmin, x);
                cmax = std::max(cmax, x);
            }
        }
    }

    if (rmax < 0 || cmax < 0) {
        return arr.clone();
    }
    return arr(cv::Range(rmin, rmax + 1), cv::Range(cmin, cmax + 1)).clone();
}

cv::Mat remove_background(const cv::Mat &arr, int tolerance) {
    const int h = arr.rows;
    const int w = arr.cols;

    std::unordered_map<int, int> border_counts;
    auto pack = [](const cv::Vec3b &p) {
        return (static_cast<int>(p[0]) << 16) | (static_cast<int>(p[1]) << 8) | static_cast<int>(p[2]);
    };

    for (int x = 0; x < w; ++x) {
        border_counts[pack(arr.at<cv::Vec3b>(0, x))]++;
        border_counts[pack(arr.at<cv::Vec3b>(h - 1, x))]++;
    }
    for (int y = 0; y < h; ++y) {
        border_counts[pack(arr.at<cv::Vec3b>(y, 0))]++;
        border_counts[pack(arr.at<cv::Vec3b>(y, w - 1))]++;
    }

    int bg_color = 0;
    int bg_count = -1;
    for (const auto &kv : border_counts) {
        if (kv.second > bg_count) {
            bg_count = kv.second;
            bg_color = kv.first;
        }
    }
    const std::array<int, 3> bg = {(bg_color >> 16) & 255, (bg_color >> 8) & 255, bg_color & 255};

    cv::Mat mask(h, w, CV_8U, cv::Scalar(0));
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            const cv::Vec3b p = arr.at<cv::Vec3b>(y, x);
            if (std::abs(static_cast<int>(p[0]) - bg[0]) <= tolerance &&
                std::abs(static_cast<int>(p[1]) - bg[1]) <= tolerance &&
                std::abs(static_cast<int>(p[2]) - bg[2]) <= tolerance) {
                mask.at<unsigned char>(y, x) = 1;
            }
        }
    }

    cv::Mat visited(h, w, CV_8U, cv::Scalar(0));
    cv::Mat flood(h, w, CV_8U, cv::Scalar(0));
    std::vector<std::pair<int, int>> q;
    q.reserve(static_cast<size_t>(h + w) * 2);

    for (int x = 0; x < w; ++x) {
        if (mask.at<unsigned char>(0, x)) q.emplace_back(0, x);
        if (mask.at<unsigned char>(h - 1, x)) q.emplace_back(h - 1, x);
    }
    for (int y = 0; y < h; ++y) {
        if (mask.at<unsigned char>(y, 0)) q.emplace_back(y, 0);
        if (mask.at<unsigned char>(y, w - 1)) q.emplace_back(y, w - 1);
    }

    size_t qi = 0;
    while (qi < q.size()) {
        auto [y, x] = q[qi++];
        if (visited.at<unsigned char>(y, x)) continue;
        visited.at<unsigned char>(y, x) = 1;
        if (!mask.at<unsigned char>(y, x)) continue;
        flood.at<unsigned char>(y, x) = 1;
        if (y > 0 && !visited.at<unsigned char>(y - 1, x) && mask.at<unsigned char>(y - 1, x)) q.emplace_back(y - 1, x);
        if (y + 1 < h && !visited.at<unsigned char>(y + 1, x) && mask.at<unsigned char>(y + 1, x)) q.emplace_back(y + 1, x);
        if (x > 0 && !visited.at<unsigned char>(y, x - 1) && mask.at<unsigned char>(y, x - 1)) q.emplace_back(y, x - 1);
        if (x + 1 < w && !visited.at<unsigned char>(y, x + 1) && mask.at<unsigned char>(y, x + 1)) q.emplace_back(y, x + 1);
    }

    cv::Mat rgba(h, w, CV_8UC4);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            const cv::Vec3b p = arr.at<cv::Vec3b>(y, x);
            cv::Vec4b out;
            out[0] = p[0];
            out[1] = p[1];
            out[2] = p[2];
            out[3] = flood.at<unsigned char>(y, x) ? 0 : 255;
            rgba.at<cv::Vec4b>(y, x) = out;
        }
    }
    return rgba;
}

bool block_uniform(const cv::Mat &arr, int ox, int oy, int kx, int ky, int true_w, int true_h, int tolerance) {
    for (int ty = 0; ty < true_h; ++ty) {
        for (int tx = 0; tx < true_w; ++tx) {
            const int y0 = oy + ty * ky;
            const int x0 = ox + tx * kx;
            const cv::Vec3b first = arr.at<cv::Vec3b>(y0, x0);
            for (int y = 0; y < ky; ++y) {
                for (int x = 0; x < kx; ++x) {
                    const cv::Vec3b p = arr.at<cv::Vec3b>(y0 + y, x0 + x);
                    if (tolerance == 0) {
                        if (p != first) return false;
                    } else {
                        if (std::abs(static_cast<int>(p[0]) - static_cast<int>(first[0])) > tolerance ||
                            std::abs(static_cast<int>(p[1]) - static_cast<int>(first[1])) > tolerance ||
                            std::abs(static_cast<int>(p[2]) - static_cast<int>(first[2])) > tolerance) {
                            return false;
                        }
                    }
                }
            }
        }
    }
    return true;
}

std::pair<int, int> find_integer_block_scale(const cv::Mat &arr, bool require_square, int tolerance, int max_checks) {
    const int h = arr.rows;
    const int w = arr.cols;
    auto div_w = divisors(w);
    auto div_h = divisors(h);
    std::sort(div_w.begin(), div_w.end(), std::greater<int>());
    std::sort(div_h.begin(), div_h.end(), std::greater<int>());

    int checks = 0;
    for (int kx : div_w) {
        for (int ky : div_h) {
            if (require_square && kx != ky) continue;
            if (kx == 1 && ky == 1) continue;
            for (int oy = 0; oy < std::min(ky, h); ++oy) {
                for (int ox = 0; ox < std::min(kx, w); ++ox) {
                    if (++checks > max_checks) return {1, 1};
                    const int h0 = h - oy;
                    const int w0 = w - ox;
                    if (h0 <= 0 || w0 <= 0) continue;
                    if (h0 % ky != 0 || w0 % kx != 0) continue;
                    const int true_h = h0 / ky;
                    const int true_w = w0 / kx;
                    if (block_uniform(arr, ox, oy, kx, ky, true_w, true_h, tolerance)) {
                        return {kx, ky};
                    }
                }
            }
        }
    }
    return {1, 1};
}

int estimate_period(const cv::Mat &arr, int axis, int min_period) {
    cv::Mat gray;
    cv::cvtColor(arr, gray, cv::COLOR_BGR2GRAY);
    gray.convertTo(gray, CV_64F);

    std::vector<double> sig;
    if (axis == 1) {
        const int cols = gray.cols;
        const int rows = gray.rows;
        sig.assign(static_cast<size_t>(std::max(0, cols - 1)), 0.0);
        for (int x = 0; x < cols - 1; ++x) {
            double s = 0.0;
            for (int y = 0; y < rows; ++y) {
                s += std::abs(gray.at<double>(y, x + 1) - gray.at<double>(y, x));
            }
            sig[static_cast<size_t>(x)] = s;
        }
    } else {
        const int cols = gray.cols;
        const int rows = gray.rows;
        sig.assign(static_cast<size_t>(std::max(0, rows - 1)), 0.0);
        for (int y = 0; y < rows - 1; ++y) {
            double s = 0.0;
            for (int x = 0; x < cols; ++x) {
                s += std::abs(gray.at<double>(y + 1, x) - gray.at<double>(y, x));
            }
            sig[static_cast<size_t>(y)] = s;
        }
    }

    if (sig.empty()) return 1;

    const double mean = std::accumulate(sig.begin(), sig.end(), 0.0) / static_cast<double>(sig.size());
    for (double &v : sig) v -= mean;

    std::vector<double> ac(sig.size(), 0.0);
    for (size_t lag = 1; lag <= sig.size(); ++lag) {
        double s = 0.0;
        for (size_t i = 0; i + lag < sig.size(); ++i) {
            s += sig[i] * sig[i + lag];
        }
        ac[lag - 1] = s;
    }
    if (ac.empty()) return 1;

    std::vector<int> peaks;
    for (size_t i = 1; i + 1 < ac.size(); ++i) {
        if (ac[i] > ac[i - 1] && ac[i] > ac[i + 1]) peaks.push_back(static_cast<int>(i + 1));
    }
    if (peaks.empty()) {
        return static_cast<int>(std::distance(ac.begin(), std::max_element(ac.begin(), ac.end()))) + 1;
    }

    const double maxv = *std::max_element(ac.begin(), ac.end());
    const double thresh = maxv * 0.2;
    int best = 0;
    for (int p : peaks) {
        if (p >= min_period && ac[static_cast<size_t>(p - 1)] >= thresh) {
            if (best == 0 || p < best) best = p;
        }
    }
    if (best > 0) return best;

    for (int p : peaks) {
        if (p >= min_period) {
            if (best == 0 || p < best) best = p;
        }
    }
    if (best > 0) return best;

    return static_cast<int>(std::distance(ac.begin(), std::max_element(ac.begin(), ac.end()))) + 1;
}

cv::Mat downsample_mode(const cv::Mat &arr, int kx, int ky) {
    const int true_h = arr.rows / ky;
    const int true_w = arr.cols / kx;
    cv::Mat out(true_h, true_w, CV_8UC3, cv::Scalar(0, 0, 0));

    for (int ty = 0; ty < true_h; ++ty) {
        for (int tx = 0; tx < true_w; ++tx) {
            std::unordered_map<int, int> counts;
            int best_color = 0;
            int best_count = -1;
            for (int y = 0; y < ky; ++y) {
                for (int x = 0; x < kx; ++x) {
                    const cv::Vec3b p = arr.at<cv::Vec3b>(ty * ky + y, tx * kx + x);
                    const int packed = (static_cast<int>(p[0]) << 16) | (static_cast<int>(p[1]) << 8) | static_cast<int>(p[2]);
                    const int c = ++counts[packed];
                    if (c > best_count) {
                        best_count = c;
                        best_color = packed;
                    }
                }
            }
            out.at<cv::Vec3b>(ty, tx) = cv::Vec3b(
                static_cast<unsigned char>((best_color >> 16) & 255),
                static_cast<unsigned char>((best_color >> 8) & 255),
                static_cast<unsigned char>(best_color & 255));
        }
    }
    return out;
}

}  // namespace

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
) {
    cv::Mat src = cv::imread(path, cv::IMREAD_COLOR);
    if (src.empty()) {
        throw std::runtime_error("failed to load image: " + path);
    }

    cv::Mat cropped = crop_whitespace(src, threshold);
    cv::Mat rgba = remove_background(cropped, 10);

    auto [scale_x_guess, scale_y_guess] = find_integer_block_scale(cropped, require_square, tolerance, max_checks);
    int scale_x = scale_x_guess;
    int scale_y = scale_y_guess;
    if (scale_x <= 1 || scale_y <= 1) {
        scale_x = estimate_period(cropped, 1, 2);
        scale_y = estimate_period(cropped, 0, 2);
    }
    if (scale_x < 1) scale_x = 1;
    if (scale_y < 1) scale_y = 1;

    const int true_w = cropped.cols / scale_x;
    const int true_h = cropped.rows / scale_y;

    fs::path in_path(path);
    std::string out_base = out_name.empty() ? (in_path.stem().string() + "_" + std::to_string(true_w) + "x" + std::to_string(true_h)) : out_name;

    std::string fmt = out_format;
    std::transform(fmt.begin(), fmt.end(), fmt.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (fmt != "png" && fmt != "bmp") {
        throw std::runtime_error("unsupported out_format: " + out_format);
    }

    fs::path out_root = out_dir.empty() ? in_path.parent_path() : fs::path(out_dir);
    fs::create_directories(out_root);
    fs::path out_path = out_root / (out_base + "." + fmt);

    if (verbose) {
        std::cout << in_path.filename().string() << ": scale " << scale_x << "x" << scale_y
                  << " -> " << true_w << "x" << true_h << ", saving " << out_path.filename().string() << std::endl;
    }

    if (write_downsample) {
        cv::Mat rgb_for_detection;
        cv::cvtColor(rgba, rgb_for_detection, cv::COLOR_BGRA2BGR);
        cv::Mat small = downsample_mode(rgb_for_detection, scale_x, scale_y);

        cv::Mat alpha = cv::Mat::zeros(true_h, true_w, CV_8U);
        for (int ty = 0; ty < true_h; ++ty) {
            for (int tx = 0; tx < true_w; ++tx) {
                int sum = 0;
                for (int y = 0; y < scale_y; ++y) {
                    for (int x = 0; x < scale_x; ++x) {
                        sum += static_cast<int>(rgba.at<cv::Vec4b>(ty * scale_y + y, tx * scale_x + x)[3]);
                    }
                }
                const int total = scale_x * scale_y;
                const int mean = total > 0 ? (sum / total) : 0;
                alpha.at<unsigned char>(ty, tx) = mean > 127 ? 255 : 0;
            }
        }

        if (fmt == "png") {
            cv::Mat out_rgba(true_h, true_w, CV_8UC4);
            for (int y = 0; y < true_h; ++y) {
                for (int x = 0; x < true_w; ++x) {
                    const cv::Vec3b p = small.at<cv::Vec3b>(y, x);
                    out_rgba.at<cv::Vec4b>(y, x) = cv::Vec4b(p[0], p[1], p[2], alpha.at<unsigned char>(y, x));
                }
            }
            cv::imwrite(out_path.string(), out_rgba);
        } else {
            cv::Mat out_rgb = small.clone();
            for (int y = 0; y < true_h; ++y) {
                for (int x = 0; x < true_w; ++x) {
                    if (alpha.at<unsigned char>(y, x) == 0) {
                        out_rgb.at<cv::Vec3b>(y, x) = cv::Vec3b(255, 255, 255);
                    }
                }
            }
            cv::imwrite(out_path.string(), out_rgb);
        }
    }

    return ProcessResult{scale_x, scale_y, true_w, true_h, out_path.string()};
}

}  // namespace truescaler

PYBIND11_MODULE(_truescaler_core, m) {
    m.doc() = "TrueScaler C++ backend";

    m.def(
        "process_file_cpp",
        [](const std::string &path,
           const std::string &out_dir,
           const std::string &out_name,
           int threshold,
           int tolerance,
           bool require_square,
           int max_checks,
           bool write_downsample,
           bool verbose,
           const std::string &out_format) {
            auto res = truescaler::process_file_cpp(
                path,
                out_dir,
                out_name,
                threshold,
                tolerance,
                require_square,
                max_checks,
                write_downsample,
                verbose,
                out_format);
            py::dict d;
            d["scale_x"] = res.scale_x;
            d["scale_y"] = res.scale_y;
            d["true_w"] = res.true_w;
            d["true_h"] = res.true_h;
            d["out"] = res.out;
            return d;
        },
        py::arg("path"),
        py::arg("out_dir") = "",
        py::arg("out_name") = "",
        py::arg("threshold") = 245,
        py::arg("tolerance") = 0,
        py::arg("require_square") = false,
        py::arg("max_checks") = 10000,
        py::arg("write_downsample") = true,
        py::arg("verbose") = true,
        py::arg("out_format") = "png");
}
