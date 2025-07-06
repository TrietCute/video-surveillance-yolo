package com.example.frontend.controller;

import com.example.frontend.model.Camera;
import com.example.frontend.model.Room;
import com.example.frontend.service.ApiService;
import javafx.fxml.FXML;
import javafx.geometry.Pos;
import javafx.scene.Node;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.stage.FileChooser;

import java.io.File;
import java.io.IOException;
import java.util.List;

public class MainController {

    @FXML
    private TextField roomNameInput;
    @FXML
    private VBox roomListContainer;

    private final ApiService apiService = new ApiService();

    @FXML
    private void initialize() {
        loadRooms();
    }

    private void loadRooms() {
        roomListContainer.getChildren().clear();
        try {
            List<Room> rooms = apiService.getRooms();
            for (Room room : rooms) {
                addRoomToUI(room);
            }
        } catch (IOException e) { // <-- Đã xóa InterruptedException
            e.printStackTrace();
            showAlert(Alert.AlertType.ERROR, "Lỗi", "Không thể tải danh sách phòng từ server.");
        }
    }

    @FXML
    private void handleAddRoom() {
        String name = roomNameInput.getText().trim();
        if (name.isEmpty()) {
            showAlert(Alert.AlertType.WARNING, "Cảnh báo", "Tên phòng không được để trống.");
            return;
        }
        try {
            Room newRoom = apiService.addRoom(name);
            addRoomToUI(newRoom);
            roomNameInput.clear();
        } catch (IOException e) { // <-- Đã xóa InterruptedException
            e.printStackTrace();
            // Cải thiện thông báo lỗi để hiển thị chi tiết từ server
            showAlert(Alert.AlertType.ERROR, "Lỗi", "Không thể thêm phòng mới.\nChi tiết: " + e.getMessage());
        }
    }

    // Trong file MainController.java

    private void addRoomToUI(Room room) {
        TitledPane roomPane = new TitledPane();
        roomPane.setAnimated(true);
        roomPane.setExpanded(false);

        Label roomNameLabel = new Label(room.getName());
        roomNameLabel.setStyle("-fx-font-size: 14px; -fx-font-weight: bold;");

        Region spacer = new Region();
        HBox.setHgrow(spacer, Priority.ALWAYS);

        Button renameBtn = new Button("Đổi tên"); // Sẽ làm ở Phần 2
        Button deleteBtn = new Button("Xóa");
        deleteBtn.setStyle("-fx-background-color: #dc3545; -fx-text-fill: white;");

        // --- THÊM SỰ KIỆN CHO NÚT XÓA ---
        deleteBtn.setOnAction(e -> {
            // Hiển thị hộp thoại xác nhận
            Alert confirmation = new Alert(Alert.AlertType.CONFIRMATION);
            confirmation.setTitle("Xác nhận xóa");
            confirmation.setHeaderText("Bạn có chắc chắn muốn xóa phòng '" + room.getName() + "' không?");
            confirmation.setContentText("Hành động này không thể hoàn tác.");

            confirmation.showAndWait().ifPresent(response -> {
                if (response == ButtonType.OK) {
                    try {
                        apiService.deleteRoom(room.getId());
                        // Xóa TitledPane khỏi giao diện
                        roomListContainer.getChildren().remove(roomPane);
                    } catch (IOException ex) {
                        ex.printStackTrace();
                        showAlert(Alert.AlertType.ERROR, "Lỗi", "Không thể xóa phòng.\nChi tiết: " + ex.getMessage());
                    }
                }
            });
        });

        // --- THÊM SỰ KIỆN CHO NÚT ĐỔI TÊN ---
        renameBtn.setOnAction(e -> {
            TextInputDialog dialog = new TextInputDialog(room.getName());
            dialog.setTitle("Đổi tên phòng");
            dialog.setHeaderText("Nhập tên mới cho phòng '" + room.getName() + "'.");
            dialog.setContentText("Tên mới:");

            dialog.showAndWait().ifPresent(newName -> {
                if (newName != null && !newName.trim().isEmpty()) {
                    try {
                        Room updatedRoom = apiService.updateRoom(room.getId(), newName.trim());
                        // Cập nhật tên trên giao diện
                        room.setName(updatedRoom.getName());
                        roomNameLabel.setText(updatedRoom.getName());
                    } catch (IOException ex) {
                        ex.printStackTrace();
                        showAlert(Alert.AlertType.ERROR, "Lỗi",
                                "Không thể đổi tên phòng.\nChi tiết: " + ex.getMessage());
                    }
                }
            });
        });

        HBox titleBox = new HBox(10, roomNameLabel, spacer, renameBtn, deleteBtn);
        titleBox.setAlignment(Pos.CENTER_LEFT);
        roomPane.setGraphic(titleBox);

        VBox contentBox = createRoomContent(room, roomPane);
        roomPane.setContent(contentBox);

        roomPane.expandedProperty().addListener((obs, wasExpanded, isNowExpanded) -> {
            if (isNowExpanded) {
                loadCamerasForRoom(room, (VBox) contentBox.lookup("#cameraContainer"));
            }
        });

        roomListContainer.getChildren().add(roomPane);
    }

    private VBox createRoomContent(Room room, TitledPane parentPane) {
        VBox cameraContainer = new VBox(10);
        cameraContainer.setId("cameraContainer");

        TextField urlInput = new TextField();
        urlInput.setPromptText("Nhập URL camera...");
        HBox.setHgrow(urlInput, Priority.ALWAYS);

        Button addCamBtn = new Button("Thêm Camera");
        addCamBtn.setOnAction(e -> {
            String url = urlInput.getText().trim();
            if (url.isEmpty())
                return;
            try {
                apiService.addCameraToRoom(room.getId(), url);
                urlInput.clear();
                loadCamerasForRoom(room, cameraContainer);
            } catch (IOException ex) { // <-- Đã xóa InterruptedException
                ex.printStackTrace();
                showAlert(Alert.AlertType.ERROR, "Lỗi", "Không thể thêm camera.");
            }
        });

        HBox addCameraBox = new HBox(10, urlInput, addCamBtn);
        VBox content = new VBox(15, addCameraBox, new Separator(), cameraContainer);
        content.setPadding(new javafx.geometry.Insets(15));
        return content;
    }

    private void loadCamerasForRoom(Room room, VBox container) {
        container.getChildren().clear();
        try {
            List<Camera> cameras = apiService.getCamerasInRoom(room.getId());
            for (Camera camera : cameras) {
                container.getChildren().add(createCameraRow(camera, room, container));
            }
        } catch (IOException e) { // <-- Đã xóa InterruptedException
            e.printStackTrace();
            container.getChildren().add(new Label("Lỗi tải danh sách camera."));
        }
    }

    private Node createCameraRow(Camera camera, Room room, VBox parentContainer) {
        Label nameLabel = new Label(room.getName());
        nameLabel.setStyle("-fx-font-weight: bold;");
        Label urlLabel = new Label(camera.getUrl());
        urlLabel.setStyle("-fx-font-size: 11px; -fx-text-fill: #666;");
        VBox infoBox = new VBox(2, nameLabel, urlLabel);

        Button yoloBtn = new Button("Xem YOLO");
        yoloBtn.setOnAction(e -> {
            System.out.println("URL camera: " + camera.getUrl());
            YoloView.open(camera.getUrl(), room.getId(), camera.getId());
        });
        

        Button detailBtn = new Button("Chi tiết");
        detailBtn.setOnAction(e -> {DetailView.open(camera, () -> loadCamerasForRoom(room, parentContainer)); });
        Button deleteBtn = new Button("Xóa");
        GridPane gridPane = new GridPane();
        deleteBtn.setOnAction(e -> {
            Alert confirmation = new Alert(Alert.AlertType.CONFIRMATION);
            confirmation.setTitle("Xác nhận xóa");
            confirmation.setHeaderText("Xóa camera có URL: " + camera.getUrl() + "?");
            confirmation.showAndWait().ifPresent(response -> {
                if (response == ButtonType.OK) {
                    try {
                        // SỬA LẠI Ở ĐÂY: Truyền vào camera.getUrl() thay vì camera.getId()
                        apiService.deleteCamera(camera.getUrl());
                        
                        parentContainer.getChildren().remove(gridPane);
                    } catch (IOException ex) {
                        showAlert(Alert.AlertType.ERROR, "Lỗi", "Không thể xóa camera.\n" + ex.getMessage());
                    }
                }
            });
        });
        HBox buttonBox = new HBox(10, yoloBtn, detailBtn, deleteBtn);
        buttonBox.setAlignment(Pos.CENTER_RIGHT);
        gridPane.add(infoBox, 0, 0);
        gridPane.add(buttonBox, 1, 0);
        ColumnConstraints col1 = new ColumnConstraints();
        col1.setPercentWidth(60);
        ColumnConstraints col2 = new ColumnConstraints();
        col2.setPercentWidth(40);
        gridPane.getColumnConstraints().addAll(col1, col2);
        gridPane.setStyle("-fx-padding: 8; -fx-background-color: #fff; -fx-border-color: #e0e0e0; -fx-border-radius: 4;");
        return gridPane;
    }

    @FXML
    private void handleTestWithVideo() {
        FileChooser fileChooser = new FileChooser();
        fileChooser.setTitle("Chọn một file video để kiểm tra");
        File file = fileChooser.showOpenDialog(roomListContainer.getScene().getWindow());
        if (file != null) {
            YoloView.open(file.getAbsolutePath(), "test-room", "test-camera");
        }
    }

    private void showAlert(Alert.AlertType type, String title, String content) {
        Alert alert = new Alert(type);
        alert.setTitle(title);
        alert.setHeaderText(null);
        alert.setContentText(content);
        alert.showAndWait();
    }
}