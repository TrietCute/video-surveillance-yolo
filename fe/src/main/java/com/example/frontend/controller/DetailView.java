package com.example.frontend.controller;

import com.example.frontend.model.Camera;
import com.example.frontend.service.ApiService;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.Label;
import javafx.scene.control.ListView;
import javafx.scene.control.TextInputDialog;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;

import java.awt.Desktop;
import java.io.File;
import java.io.IOException;
import java.util.List;

public class DetailView {
    public DetailView() { }

    // THÊM THAM SỐ Runnable onUpdateSuccess
    public static void open(Camera camera, Runnable onUpdateSuccess) {
        Stage stage = new Stage();
        stage.setTitle("Chi tiết cho Camera ID: " + camera.getId());

        VBox root = new VBox(10);
        root.setPadding(new Insets(15));
        root.setAlignment(Pos.CENTER);

        Label titleLabel = new Label("Danh sách video sự kiện đã ghi");
        titleLabel.setStyle("-fx-font-size: 16px; -fx-font-weight: bold;");

        ListView<String> videoListView = new ListView<>();

        try {
            ApiService apiService = new ApiService();
            List<String> videoPaths = apiService.getEventVideos(camera.getId());
            if (videoPaths.isEmpty()) {
                videoListView.getItems().add("Không có video sự kiện nào được ghi lại.");
            } else {
                videoListView.getItems().addAll(videoPaths);
            }
        } catch (Exception e) {
            e.printStackTrace();
            videoListView.getItems().add("Lỗi khi tải danh sách video.");
        }

        Button openBtn = new Button("Mở video");
        openBtn.setOnAction(e -> {
            String selectedPath = videoListView.getSelectionModel().getSelectedItem();
            if (selectedPath != null && !selectedPath.contains("Lỗi") && !selectedPath.contains("Không có")) {
                try {
                    // Đường dẫn tương đối từ thư mục gốc của dự án
                    File projectRoot = new File(System.getProperty("user.dir")).getParentFile();
                    // Tạo đường dẫn tuyệt đối chính xác đến file video trong thư mục backend ('be')
                    File videoFile = new File(projectRoot, "be/" + selectedPath);
                    if (!videoFile.exists()) {
                        showAlert("Lỗi", "Không tìm thấy file: " + videoFile.getCanonicalPath());
                        return;
                    }
                    if (Desktop.isDesktopSupported()) {
                        Desktop.getDesktop().open(videoFile.getCanonicalFile());
                    }
                } catch (IOException ex) {
                    ex.printStackTrace();
                    showAlert("Lỗi", "Không thể mở file: " + ex.getMessage());
                }
            }
        });

        Button editUrlBtn = new Button("Sửa URL");
        editUrlBtn.setOnAction(e -> {
            TextInputDialog dialog = new TextInputDialog(camera.getUrl());
            dialog.setTitle("Sửa URL Camera");
            dialog.setHeaderText("Nhập URL mới cho camera.");
            dialog.setContentText("URL:");

            dialog.showAndWait().ifPresent(newUrl -> {
                if (newUrl != null && !newUrl.trim().isEmpty()) {
                    try {
                        ApiService apiService = new ApiService();
                        apiService.updateCameraUrl(camera.getId(), newUrl.trim());
                        if (onUpdateSuccess != null) {
                            onUpdateSuccess.run();
                        }
 
                        stage.close(); 
                    } catch (IOException ex) {
                        showAlert("Lỗi", "Không thể cập nhật URL.\n" + ex.getMessage());
                    }
                }
            });
        });

        HBox buttonBox = new HBox(10, openBtn, editUrlBtn);
        buttonBox.setAlignment(Pos.CENTER);

        root.getChildren().addAll(titleLabel, videoListView, buttonBox);

        Scene scene = new Scene(root, 500, 400);
        stage.setScene(scene);
        stage.show();
    }

    private static void showAlert(String title, String content) {
        Alert alert = new Alert(Alert.AlertType.ERROR);
        alert.setTitle(title);
        alert.setHeaderText(null);
        alert.setContentText(content);
        alert.showAndWait();
    }
}