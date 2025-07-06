package com.example.frontend.controller;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

import javax.imageio.ImageIO;

import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.Frame;
import org.bytedeco.javacv.Java2DFrameConverter;

import com.example.frontend.service.VideoWebSocketClient;

import javafx.application.Platform;
import javafx.embed.swing.SwingFXUtils;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.StackPane;
import javafx.stage.Stage;

public class YoloView {

    private static VideoWebSocketClient wsClient;
    private static ScheduledExecutorService executor;
    private static FFmpegFrameGrabber grabber;

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

        try {
            if (streamUrl == null || streamUrl.isEmpty() || streamUrl.length() < 6
                    || !(streamUrl.startsWith("http") || new File(streamUrl).exists())) {
                throw new IllegalArgumentException("URL không hợp lệ: " + streamUrl);
            }
            grabber = new FFmpegFrameGrabber(streamUrl);
            grabber.start();

            wsClient = new VideoWebSocketClient(
                    (BufferedImage bufferedImage) -> {
                        Platform.runLater(() -> {
                            Image fxImage = SwingFXUtils.toFXImage(bufferedImage, null);
                            imageView.setImage(fxImage);
                        });
                    });
            // wsClient.connect("ws://localhost:8000/ws/video");
            wsClient.connect("ws://localhost:8000/ws/video?cam_id="+cameraId);

            executor = Executors.newSingleThreadScheduledExecutor();
            Runnable frameSender = () -> {
                try {
                    Frame frame = grabber.grab();
                    if (frame != null && frame.image != null) {
                        BufferedImage bImage = new Java2DFrameConverter().convert(frame);
                        if (bImage != null) {
                            ByteArrayOutputStream baos = new ByteArrayOutputStream();
                            ImageIO.write(bImage, "jpg", baos);
                            wsClient.sendFrame(baos.toByteArray());
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            };

            executor.scheduleAtFixedRate(frameSender, 0, 33, TimeUnit.MILLISECONDS);

        } catch (Exception e) {
            e.printStackTrace();
        }

        stage.setOnCloseRequest(event -> stopEverything());
        stage.show();
    }

    private static void stopEverything() {
        try {
            if (executor != null && !executor.isShutdown()) {
                executor.shutdown();
            }
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
