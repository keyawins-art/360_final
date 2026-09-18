#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "cashew_segmentation.hpp"

namespace py = pybind11;

PYBIND11_MODULE(cashew_segmentation_core, m) {
    m.doc() = "Ultra-fast C++ OpenCV Segmentation Module for Cashew Sorting";

    py::class_<CashewSegmentation>(m, "CashewSegmentation")
        .def(py::init<int, double, int, int, int, int, int, int>(),
             py::arg("min_area") = 3500,
             py::arg("min_density") = 0.15,
             py::arg("h_min") = 0, py::arg("h_max") = 40,
             py::arg("s_min") = 30, py::arg("s_max") = 255,
             py::arg("v_min") = 15, py::arg("v_max") = 255)
        .def("segment_zone", [](CashewSegmentation& self, py::array_t<uint8_t> zone_array, int x_off, int y_off) {
            py::buffer_info buf = zone_array.request();
            if (buf.ndim != 3 || buf.shape[2] != 3) {
                throw std::runtime_error("Input frame must be 3-channel BGR numpy array");
            }
            cv::Mat mat(buf.shape[0], buf.shape[1], CV_8UC3, (unsigned char*)buf.ptr);
            return self.segment_zone(mat, x_off, y_off);
        }, py::arg("zone_bgr"), py::arg("zone_x_offset") = 0, py::arg("zone_y_offset") = 0);
}
