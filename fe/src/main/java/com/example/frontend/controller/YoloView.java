package com.example.frontend.controller;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import javax.imageio.ImageIO;

import org.bytedeco.javacv.FFmpegFrameGrabber;
import org.bytedeco.javacv.Frame;
import org.bytedeco.javacv.Java2DFrameConverter;

import com.example.frontend.service.VideoWebSocketClient;

import javafx.application.Platform;
import javafx.embed.swing.SwingFXUtils;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.image.ImageView;
import javafx.scene.layout.HBox;
import javafx.scene.layout.StackPane;
import javafx.scene.paint.Color;
import javafx.scene.text.Font;
import javafx.stage.Stage;

public class YoloView {

    public static void open(String url, String roomId, String camId) {
        Platform.runLater(() -> new YoloView(url, roomId, camId).stage.show());
    }

    private final Stage stage;
    private final VideoProcessor processor;

    private YoloView(String url, String roomId, String camId) {
        stage = new Stage();
        stage.setTitle("YOLO Monitoring - " + roomId);

        ImageView imageView = new ImageView();
        Label statusLabel = statusLabel();

        // --- Control Buttons ---
        Button btnPlayPause = new Button("▶️");
        Button btnStop = new Button("⏹");
        Button btnForward = new Button("⏩");
        Button btnRewind = new Button("⏪");

        HBox controls = new HBox(10, btnRewind, btnPlayPause, btnStop, btnForward);
        controls.setAlignment(Pos.BOTTOM_CENTER);
        controls.setStyle("-fx-background-color: transparent; -fx-padding: 10;");

        StackPane root = new StackPane(imageView, statusLabel, controls);
        Scene scene = new Scene(root, 1280, 720);

        imageView.fitWidthProperty().bind(scene.widthProperty());
        imageView.fitHeightProperty().bind(scene.heightProperty());
        imageView.setPreserveRatio(true);
        stage.setScene(scene);

        processor = new VideoProcessor(url, camId, imageView, statusLabel);
        processor.start();

        stage.setOnCloseRequest(event -> {
            processor.stop();
            stage.close();
        });

        // --- Button Events ---
        btnPlayPause.setOnAction(e -> {
            if (processor.isPaused()) {
                processor.resume();
                btnPlayPause.setText("⏸");
            } else {
                processor.pause();
                btnPlayPause.setText("▶️");
            }
        });

        btnStop.setOnAction(e -> {
            processor.stopCompletely();
            stage.close(); // Close the stage when stopped
            btnPlayPause.setText("▶️");
        });

        btnForward.setOnAction(e -> {
            processor.seekForward(10);
        });

        btnRewind.setOnAction(e -> {
            processor.seekBackward(10);
        });
    }

    private Label statusLabel() {
        Label l = new Label("Initializing...");
        l.setFont(new Font(20));
        l.setTextFill(Color.WHITE);
        l.setStyle("-fx-background-color: transparent; -fx-padding:8;");
        StackPane.setAlignment(l, Pos.TOP_CENTER);
        return l;
    }

    static class VideoProcessor {
        private final String url;
        private final String camId;
        private final ImageView imageView;
        private final Label statusLabel;
        private ExecutorService executor;
        private volatile boolean isRunning = false;
        private volatile boolean isPaused = false;
        private FFmpegFrameGrabber grabber;
        private VideoWebSocketClient wsClient;

        VideoProcessor(String url, String camId, ImageView iv, Label lb) {
            this.url = url;
            this.camId = camId;
            this.imageView = iv;
            this.statusLabel = lb;
        }

        void start() {
            isRunning = true;
            executor = Executors.newSingleThreadExecutor();
            executor.submit(this::loop);
        }

        void stop() {
            isRunning = false;
            if (executor != null) {
                executor.shutdownNow();
                try {
                    executor.awaitTermination(2, TimeUnit.SECONDS);
                } catch (InterruptedException ignored) {
                }
            }
        }

        void stopCompletely() {
            stop();
            updateStatus("Stopped");
        }

        void pause() {
            isPaused = true;
            updateStatus("Paused");
        }

        void resume() {
            isPaused = false;
            updateStatus("Streaming...");
        }

        boolean isPaused() {
            return isPaused;
        }

        void seekForward(int seconds) {
            try {
                long targetTimestamp = grabber.getTimestamp() + seconds * 1_000_000L;
                grabber.setTimestamp(targetTimestamp);
                updateStatus("⏩ " + seconds + "s");
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        void seekBackward(int seconds) {
            try {
                long targetTimestamp = Math.max(grabber.getTimestamp() - seconds * 1_000_000L, 0);
                grabber.setTimestamp(targetTimestamp);
                updateStatus("⏪ " + seconds + "s");
            } catch (Exception e) {
                e.printStackTrace();
            }
        }

        private void loop() {
            try (Java2DFrameConverter converter = new Java2DFrameConverter()) {
                updateStatus("Connecting...");
                grabber = new FFmpegFrameGrabber(url);
                grabber.setOption("rtsp_transport", "tcp");
                grabber.setAudioChannels(0);
                grabber.start();

                double fps = grabber.getVideoFrameRate();
                if (fps <= 1) fps = 25;
                long frameDurationMillis = Math.round(1000.0 / fps);

                wsClient = new VideoWebSocketClient(img -> {
                    Platform.runLater(() -> imageView.setImage(SwingFXUtils.toFXImage(img, null)));
                });
                wsClient.connect("ws://localhost:8000/ws/video?cam_id=" + camId);

                updateStatus("Streaming...");

                long lastFrameTime = System.currentTimeMillis();

                boolean shouldRun = true;
                while (isRunning && shouldRun) {
                    if (isPaused) {
                        try {
                            TimeUnit.MILLISECONDS.sleep(100);
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                            break;
                        }
                        continue;
                    }

                    Frame frame = grabber.grabImage();
                    if (frame == null) {
                        shouldRun = false;
                    } else {
                        BufferedImage image = converter.convert(frame);
                        if (image != null && wsClient != null && isRunning) {
                            ByteArrayOutputStream baos = new ByteArrayOutputStream();
                            ImageIO.write(image, "jpg", baos);
                            wsClient.sendFrame(baos.toByteArray());

                            Platform.runLater(() -> imageView.setImage(SwingFXUtils.toFXImage(image, null)));
                        }

                        long now = System.currentTimeMillis();
                        long elapsed = now - lastFrameTime;
                        long delay = frameDurationMillis - elapsed;
                        if (delay > 0) Thread.sleep(delay);
                        lastFrameTime = System.currentTimeMillis();
                    }
                }

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                System.out.println("Video thread interrupted.");
            } catch (Exception e) {
                e.printStackTrace();
                updateStatus("Error: " + e.getMessage());
            } finally {
                cleanup();
            }
        }

        private void updateStatus(String message) {
            Platform.runLater(() -> statusLabel.setText(message));
        }

        private void cleanup() {
            try {
                if (wsClient != null) {
                    wsClient.close();
                    wsClient = null;
                }
            } catch (Exception e) {
                e.printStackTrace();
            }

            try {
                if (grabber != null) {
                    grabber.stop();
                    grabber.release();
                    grabber = null;
                }
            } catch (Exception e) {
                e.printStackTrace();
            }

            updateStatus("Stopped");
        }
    }
}
