package com.example.frontend.controller;

import java.awt.image.BufferedImage;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.bytedeco.javacpp.BytePointer;
import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.Frame;
import org.bytedeco.javacv.OpenCVFrameConverter;
import static org.bytedeco.opencv.global.opencv_imgcodecs.imencode;
import org.bytedeco.opencv.opencv_core.Mat;

import com.example.frontend.service.VideoWebSocketClient;

import javafx.application.Platform;
import javafx.embed.swing.SwingFXUtils;
import javafx.scene.Scene;
import javafx.scene.image.Image; // <-- Import hàm nén ảnh nhanh hơn
import javafx.scene.image.ImageView;
import javafx.scene.layout.StackPane;
import javafx.stage.Stage;

public class YoloView {

    private static VideoWebSocketClient wsClient;
    // Sử dụng ExecutorService thay vì ScheduledExecutorService
    private static ExecutorService executor;
    private static FFmpegFrameGrabber grabber;
    // Biến cờ để điều khiển vòng lặp
    private static volatile boolean isRunning = true;

    public static void open(String streamUrl, String roomId, String cameraId) {
        Stage stage = new Stage();
        stage.setTitle("Màn hình Giám sát YOLO - Phòng: " + roomId);

        ImageView imageView = new ImageView();
        StackPane root = new StackPane(imageView);
        Scene scene = new Scene(root, 1280, 720);

        imageView.fitWidthProperty().bind(scene.widthProperty());
        imageView.fitHeightProperty().bind(scene.heightProperty());
        imageView.setPreserveRatio(true);

        stage.setScene(scene);

        // Tạo một luồng duy nhất để xử lý tất cả
        executor = Executors.newSingleThreadExecutor();
        executor.submit(() -> {
            try {
                // --- Toàn bộ logic nặng được đưa vào luồng này ---
                grabber = new FFmpegFrameGrabber(streamUrl);
                grabber.start();

                wsClient = new VideoWebSocketClient(
                    (BufferedImage bufferedImage) -> {
                        if (bufferedImage != null) {
                            Platform.runLater(() -> {
                                Image fxImage = SwingFXUtils.toFXImage(bufferedImage, null);
                                imageView.setImage(fxImage);
                            });
                        }
                    }
                );
                 wsClient.connect("ws://localhost:8000/ws/video?cam_id="+cameraId);

                // Sử dụng converter của OpenCV
                OpenCVFrameConverter.ToMat toMatConverter = new OpenCVFrameConverter.ToMat();

                // Vòng lặp xử lý video, đảm bảo xử lý xong frame này mới lấy frame tiếp theo
                while (isRunning && !Thread.currentThread().isInterrupted()) {
                    Frame frame = grabber.grab();
                    if (frame == null) {
                        break; // Kết thúc nếu hết video
                    }

                    Mat mat = toMatConverter.convert(frame);
                    if (mat != null) {
                        BytePointer buf = new BytePointer();
                        // --- SỬ DỤNG imencode NHANH HƠN RẤT NHIỀU ---
                        imencode(".jpg", mat, buf);
                        
                        byte[] jpegBytes = new byte[(int) buf.limit()];
                        buf.get(jpegBytes);
                        
                        if (wsClient != null) {
                            wsClient.sendFrame(jpegBytes);
                        }
                        buf.close();
                    }
                }
            } catch (Exception e) {
                e.printStackTrace();
            } finally {
                // Dọn dẹp khi luồng kết thúc
                stopEverything();
            }
        });

        stage.setOnCloseRequest(event -> stopEverything());
        stage.show();
    }

    private static void stopEverything() {
        isRunning = false; // Đặt cờ để dừng vòng lặp
        if (executor != null && !executor.isShutdown()) {
            executor.shutdownNow(); // Ngắt luồng ngay lập tức
        }
        try {
            if (wsClient != null) {
                wsClient.close();
            }
            if (grabber != null) {
                grabber.stop();
                grabber.release();
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}