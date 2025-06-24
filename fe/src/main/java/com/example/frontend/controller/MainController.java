package com.example.frontend.controller;

import com.example.frontend.service.CameraService;
import javafx.fxml.FXML;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import java.util.List;

public class MainController {

    @FXML
    private TextField cameraUrlInput;

    @FXML
    private VBox cameraListContainer;

    @FXML
    private void initialize() {
        try {
            List<String> cameras = CameraService.fetchCameraList();

            boolean hasLocal = cameras.contains("local") || cameras.contains("0");
            if (!hasLocal) {
                CameraService.addCamera("local");
                addCameraToUI("local");
            } else {
                // Nếu đã có "local" thì thêm vào UI
                if (cameras.contains("local")) {
                    addCameraToUI("local");
                } else if (cameras.contains("0")) {
                    addCameraToUI("0");
                }
            }

            for (String camUrl : cameras) {
                // Đã xử lý "local" phía trên, nên bỏ qua tại đây
                if (!camUrl.equals("local") && !camUrl.equals("0")) {
                    addCameraToUI(camUrl);
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
            addCameraToUI(url);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void addCameraToUI(String url) {
        Label label = new Label(url);
        label.setStyle("-fx-font-size: 14px; -fx-text-fill: #555;");
        label.setWrapText(true);
        label.setMaxWidth(350);

        Button actionBtn = new Button("▶ Xem trực tiếp");
        actionBtn.setStyle("-fx-background-color: #2196F3; -fx-text-fill: white;");

        Button detailBtn = new Button("📂 Xem chi tiết");
        detailBtn.setStyle("-fx-background-color: #FFC107; -fx-text-fill: black;");

        Button deleteBtn = new Button("🗑 Xóa");
        deleteBtn.setStyle("-fx-background-color: #F44336; -fx-text-fill: white;");

        final boolean[] isStreaming = { false };

        actionBtn.setOnAction(e -> {
            try {
                if (!isStreaming[0]) {
                    // Bắt đầu stream + mở trình duyệt
                    CameraService.startStream(url);
                    showAlert("Đã bắt đầu phát hiện đối tượng.");
                    actionBtn.setText("⏹ Dừng");
                    isStreaming[0] = true;
                } else {
                    // Dừng stream
                    CameraService.stopStream(url);
                    showAlert("Đã dừng stream và lưu dữ liệu.");
                    actionBtn.setText("▶ Xem trực tiếp");
                    isStreaming[0] = false;
                }
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        detailBtn.setOnAction(e -> {
            try {
                DetailView.open(url); // Xem phần dưới để tạo class này
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        deleteBtn.setOnAction(e -> {
            try {
                CameraService.deleteCamera(url);
                cameraListContainer.getChildren().remove(((Button) e.getSource()).getParent());
            } catch (Exception ex) {
                ex.printStackTrace();
            }
        });

        HBox buttonBox = new HBox(10, label, actionBtn, detailBtn, deleteBtn);

        buttonBox.setStyle("-fx-alignment: CENTER_RIGHT;");

        GridPane row = new GridPane();
        row.setHgap(10);
        row.setVgap(5);
        row.setStyle("-fx-background-color: #fff; -fx-padding: 10; -fx-border-color: #ddd; -fx-border-radius: 5;");
        row.add(label, 0, 0);
        row.add(buttonBox, 1, 0);

        // Cột 0 chiếm 60%, cột 1 chiếm 40%
        ColumnConstraints col1 = new ColumnConstraints();
        col1.setPercentWidth(60);
        ColumnConstraints col2 = new ColumnConstraints();
        col2.setPercentWidth(40);
        row.getColumnConstraints().addAll(col1, col2);

        cameraListContainer.getChildren().add(row);
    }

    private void showAlert(String msg) {
        Alert alert = new Alert(Alert.AlertType.INFORMATION, msg);
        alert.showAndWait();
    }
}
