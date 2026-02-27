find_package(pybind11 CONFIG REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS imgcodecs imgproc)

pybind11_add_module(_truescaler_core src/core.cpp)

target_include_directories(_truescaler_core PRIVATE include)
target_link_libraries(_truescaler_core PRIVATE ${OpenCV_LIBS})

install(TARGETS _truescaler_core
  LIBRARY DESTINATION .
  RUNTIME DESTINATION .
  ARCHIVE DESTINATION .
)
