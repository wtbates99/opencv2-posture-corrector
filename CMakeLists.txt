cmake_minimum_required(VERSION 3.10)
project(PostureCorrector VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find OpenCV
find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})

# Add executable
add_executable(posture_corrector main.cpp)

# Link OpenCV libraries
target_link_libraries(posture_corrector PRIVATE ${OpenCV_LIBS})

# Static linking hint (uncomment if you want to try static builds, may require OpenCV built statically)
# set_target_properties(posture_corrector PROPERTIES LINK_FLAGS "-static")

# CPack for distribution
set(CPACK_GENERATOR "TGZ;ZIP")  # Tarball and ZIP for easy upload
set(CPACK_PACKAGE_NAME "PostureCorrector")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION "Lightweight posture correction tool using OpenCV")
set(CPACK_PACKAGE_FILE_NAME "${CPACK_PACKAGE_NAME}-${CPACK_PACKAGE_VERSION}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}")
include(CPack)

# Custom dist target
add_custom_target(dist
    COMMAND ${CMAKE_COMMAND} --build ${CMAKE_BINARY_DIR} --target package
    DEPENDS posture_corrector
)