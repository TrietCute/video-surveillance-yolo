package com.example.frontend.controller;

import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.util.List;
import java.util.Map;

import javax.imageio.ImageIO;

import org.bytedeco.javacv.Frame;
import org.bytedeco.javacv.Java2DFrameConverter;
import org.bytedeco.javacv.OpenCVFrameGrabber;

import com.example.frontend.service.CameraService;
import com.example.frontend.service.VideoWebSocketClient;

import javafx.application.Platform;
import javafx.embed.swing.SwingFXUtils;
import javafx.fxml.FXML;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.TextField;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.ColumnConstraints;
import javafx.scene.layout.GridPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.FileChooser;
import javafx.stage.Stage;


public class MainController {

    @FXML
    private TextField cameraUrlInput;

    @FXML
    private VBox cameraListContainer;
    private VideoWebSocketClient wsClient;


    @FXML
    private void initialize() {
        try {
            List<Map<String, String>> cameras = CameraService.fetchCameraList();

            // Thêm tất cả camera vào giao diện
            for (Map<String, String> cam : cameras) {
                String url = cam.get("url");
                String id = cam.get("id");
                if (url != null && !url.isEmpty()) {
                    addCameraToUI(url, id);
                }
            }

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    @FXML
    private void handleAddCamera() {
        String url = cameraUrlInput.getText();
        try {
            CameraService.addCamera(url);
            // Gọi lại fetch để lấy đúng id vừa thêm
            List<Map<String, String>> cameras = CameraService.fetchCameraList();
            for (Map<String, String> cam : cameras) {
                if (cam.get("url").equals(url)) {
                    addCameraToUI(url, cam.get("id"));
                    break;
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    @FXML private void handleAddTestVideo() {
        FileChooser chooser = new FileChooser();
        chooser.setTitle("Chọn video MP4");
        chooser.getExtensionFilters().add(new FileChooser.ExtensionFilter("MP4", "*.mp4"));
        File file = chooser.showOpenDialog(new Stage());
        if (file != null) playTestVideo(file);
    }

    private void addCameraToUI(String url, String cameraId) {
        Label label = new Label(url);
        label.setStyle("-fx-font-size: 14px; -fx-text-fill: #555;");
        label.setWrapText(true);
        label.setMaxWidth(350);

        Button streamBtn = new Button("▶ Xem trực tiếp");
        streamBtn.setStyle("-fx-background-color: #2196F3; -fx-text-fill: white;");

        Button detailBtn = new Button("📂 Xem chi tiết");
        detailBtn.setStyle("-fx-background-color: #FFC107; -fx-text-fill: black;");

        Button deleteBtn = new Button("🗑 Xóa");
        deleteBtn.setStyle("-fx-background-color: #F44336; -fx-text-fill: white;");

        streamBtn.setOnAction(e -> {
            try {
                if (streamBtn.getText().startsWith("▶")) {
                    CameraService.startStream(url);
                    showAlert("Đã bắt đầu phát hiện đối tượng.");
                    streamBtn.setText("⏹ Dừng");
                } else {
                    CameraService.stopStream(url);
                    showAlert("Đã dừng stream và lưu dữ liệu.");
                    streamBtn.setText("▶ Xem trực tiếp");
                }
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        detailBtn.setOnAction(e -> {
            try {
                DetailView.open(cameraId);
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        deleteBtn.setOnAction(e -> {
            try {
                CameraService.deleteCamera(url);
                cameraListContainer.getChildren().remove(((Button) e.getSource()).getParent().getParent());
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        HBox buttonBox = new HBox(10, streamBtn, detailBtn, deleteBtn);
        buttonBox.setStyle("-fx-alignment: CENTER_RIGHT;");

        GridPane row = new GridPane();
        row.setHgap(10);
        row.setVgap(5);
        row.setStyle("-fx-background-color: #fff; -fx-padding: 10; -fx-border-color: #ddd; -fx-border-radius: 5;");
        row.add(label, 0, 0);
        row.add(buttonBox, 1, 0);

        ColumnConstraints col1 = new ColumnConstraints();
        col1.setPercentWidth(60);
        ColumnConstraints col2 = new ColumnConstraints();
        col2.setPercentWidth(40);
        row.getColumnConstraints().addAll(col1, col2);

        cameraListContainer.getChildren().add(row);
    }
    private void showAlert(String message) {
        Alert alert = new Alert(Alert.AlertType.INFORMATION);
        alert.setTitle("Thông báo");
        alert.setHeaderText(null);
        alert.setContentText(message);
        alert.showAndWait();
    }

    private void playTestVideo(File videoFile) {
        try {
            // Mở video để đọc từng frame
            OpenCVFrameGrabber grabber = new OpenCVFrameGrabber(videoFile);
            grabber.start();

            ImageView imageView = new ImageView();
            imageView.setPreserveRatio(true);
            VBox vbox = new VBox(imageView);
            Scene scene = new Scene(vbox);
            Stage stage = new Stage();
            stage.setTitle("Phát lại video");
            stage.setScene(scene);
            stage.show();

            wsClient = new VideoWebSocketClient(frame -> {
                Platform.runLater(() -> {
                    Image fxImage = SwingFXUtils.toFXImage(frame, null);
                    imageView.setImage(fxImage);
                    stage.setWidth(fxImage.getWidth());
                    stage.setHeight(fxImage.getHeight() + 40);
                });
            });

            wsClient.connect("ws://localhost:8000/ws/video");

            Thread sender = new Thread(() -> {
                try {
                    Frame frame;
                    Java2DFrameConverter converter = new Java2DFrameConverter();
                    while ((frame = grabber.grab()) != null) {
                        BufferedImage img = converter.convert(frame);
                        ByteArrayOutputStream baos = new ByteArrayOutputStream();
                        ImageIO.write(img, "jpg", baos);
                        wsClient.sendFrame(baos.toByteArray());
                        Thread.sleep(33); // tùy theo tốc độ mong muốn
                    }
                    grabber.stop();
                    wsClient.close();
                } catch (Exception ex) {
                    ex.printStackTrace();
                }
            });
            sender.setDaemon(true);
            sender.start();

        } catch (Exception e) {
            e.printStackTrace();
            showAlert("Không thể mở video: " + e.getMessage());
        }
    }
}
