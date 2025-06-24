package com.example.frontend.controller;

import javafx.scene.Scene;
import javafx.scene.control.Label;
import javafx.scene.layout.VBox;
import javafx.stage.Stage;

public class DetailView {
    public static void open(String url) {
        VBox layout = new VBox(10);
        layout.setStyle("-fx-padding: 20");
        layout.getChildren().add(new Label("📷 Chi tiết camera: " + url));
        layout.getChildren().add(new Label("🔍 Ở đây bạn có thể hiển thị ảnh/video theo thời gian"));

        Stage stage = new Stage();
        stage.setTitle("Chi tiết camera");
        stage.setScene(new Scene(layout, 400, 200));
        stage.show();
    }
}
