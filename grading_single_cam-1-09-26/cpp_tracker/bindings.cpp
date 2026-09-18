#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "cashew_tracker.hpp"

namespace py = pybind11;

PYBIND11_MODULE(cashew_tracker_core, m) {
    m.doc() = "High-speed C++ cashew tracker with constant-velocity Kalman prediction";

    py::class_<Detection>(m, "Detection")
        .def(py::init<>())
        .def_readwrite("x", &Detection::x)
        .def_readwrite("y", &Detection::y)
        .def_readwrite("size_mm", &Detection::size_mm);

    py::class_<TrackOutput>(m, "TrackOutput")
        .def_readonly("id", &TrackOutput::id)
        .def_readonly("x", &TrackOutput::x)
        .def_readonly("y", &TrackOutput::y)
        .def_readonly("vx", &TrackOutput::vx)
        .def_readonly("vy", &TrackOutput::vy)
        .def_readonly("predicted_x", &TrackOutput::predicted_x)
        .def_readonly("predicted_y", &TrackOutput::predicted_y)
        .def_readonly("speed_px_s", &TrackOutput::speed_px_s)
        .def_readonly("missed", &TrackOutput::missed)
        .def_readonly("matched", &TrackOutput::matched)
        .def_readonly("is_new", &TrackOutput::is_new)
        .def_readonly("det_index", &TrackOutput::det_index)
        .def_readonly("track_size_mm", &TrackOutput::track_size_mm);

    py::class_<CashewTracker>(m, "CashewTracker")
        .def(
            py::init<double,double,double,int,double,double>(),
            py::arg("base_gate_px") = 120.0,
            py::arg("gate_per_sec_px") = 2500.0,
            py::arg("max_gate_px") = 320.0,
            py::arg("max_missed") = 8,
            py::arg("process_noise") = 35.0,
            py::arg("measurement_noise") = 8.0
        )
        .def("update", &CashewTracker::update,
             py::arg("detections"), py::arg("timestamp"))
        .def("get_tracks", &CashewTracker::get_tracks)
        .def("remove_track", &CashewTracker::remove_track)
        .def("reset", &CashewTracker::reset);
}
