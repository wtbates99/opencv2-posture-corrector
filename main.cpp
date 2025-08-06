#include <opencv2/opencv.hpp>
#include <iostream>
#include <chrono>
#include <thread>

int main() {
    cv::VideoCapture cap(0);  // Open default webcam
    if (!cap.isOpened()) {
        std::cerr << "Error: Could not open webcam." << std::endl;
        return -1;
    }

    std::cout << "Posture Corrector running. Press 'q' to quit." << std::endl;

    while (true) {
        cv::Mat frame;
        cap >> frame;
        if (frame.empty()) {
            std::cerr << "Error: Empty frame." << std::endl;
            break;
        }

        // Simple posture detection stub (convert to grayscale, detect edges, find lines for shoulders)
        cv::Mat gray, edges;
        cv::cvtColor(frame, gray, cv::COLOR_BGR2GRAY);
        cv::Canny(gray, edges, 50, 150);

        std::vector<cv::Vec4i> lines;
        cv::HoughLinesP(edges, lines, 1, CV_PI/180, 100, 50, 10);

        // Basic logic: If we detect roughly horizontal lines (shoulders), check alignment
        bool goodPosture = false;  // Replace with real logic
        if (!lines.empty()) {
            // Stub: Assume first line is shoulder; check angle
            float angle = std::atan2(lines[0][3] - lines[0][1], lines[0][2] - lines[0][0]) * 180 / CV_PI;
            goodPosture = (std::abs(angle) < 10);  // Less than 10 degrees tilt = good
        }

        // Feedback
        std::cout << (goodPosture ? "Good posture!" : "Straighten up!") << std::endl;

        // Optional: Show processed frame (comment out for headless)
        // cv::imshow("Posture View", frame);
        // if (cv::waitKey(1) == 'q') break;

        std::this_thread::sleep_for(std::chrono::milliseconds(500));  // Throttle to 2 FPS for efficiency
    }

    cap.release();
    return 0;
}