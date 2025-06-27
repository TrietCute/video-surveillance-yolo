package com.example.frontend.controller;

import java.awt.Desktop;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

import com.example.frontend.service.CameraService;

import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.scene.Scene;
import javafx.scene.control.Alert;
import javafx.scene.control.Button;
import javafx.scene.control.ButtonType;
import javafx.scene.control.ContextMenu;
import javafx.scene.control.Label;
import javafx.scene.control.MenuItem;
import javafx.scene.control.TreeCell;
import javafx.scene.control.TreeItem;
import javafx.scene.control.TreeView;
import javafx.scene.image.Image;
import javafx.scene.image.ImageView;
import javafx.scene.layout.BorderPane;
import javafx.scene.layout.HBox;
import javafx.scene.layout.VBox;
import javafx.scene.media.Media;
import javafx.scene.media.MediaPlayer;
import javafx.scene.media.MediaView;
import javafx.stage.Stage;
import javafx.util.Duration;

public class DetailView {

    private static final Path PROJECT_BE = Paths.get(System.getProperty("user.dir"))
            .resolveSibling("be");
    private static MediaPlayer mediaPlayer;

    private DetailView() {
    }

    public static void open(String cameraId) {
        List<String> rawPaths;
        try {
            rawPaths = CameraService.getCameraFiles(cameraId);
        } catch (IOException ex) {
            ex.printStackTrace();
            new Alert(Alert.AlertType.ERROR,
                    "Không thể lấy video từ server:\n" + ex.getMessage(),
                    ButtonType.OK).showAndWait();
            return;
        }

        // Build Tree
        TreeItem<VideoNode> root = buildTree(rawPaths);
        TreeView<VideoNode> tree = new TreeView<>(root);
        tree.setShowRoot(false);

        // Cell factory: text + thumbnail khi load xong + padding + delete menu
        tree.setCellFactory(tv -> new TreeCell<>() {
            private final ImageView thumb = new ImageView();

            @Override
            protected void updateItem(VideoNode node, boolean empty) {
                super.updateItem(node, empty);

                if (empty || node == null) {
                    setText(null);
                    setGraphic(null);
                    setContextMenu(null);
                } else if (node.isDir) {
                    setText(node.display);
                    setGraphic(null);
                    setContextMenu(null);
                    setPadding(new Insets(2, 2, 2, 8));
                } else {
                    // file leaf
                    setText(node.display);
                    setGraphic(null);
                    setPadding(new Insets(2, 2, 2, 20));

                    // chỉ đặt graphic khi thumbnail đã load
                    generateThumbnail(node, thumb, this);

                    MenuItem del = new MenuItem("❌ Xóa file");
                    del.setOnAction(e -> {
                        try {
                            // Xoá trong CSDL trước
                            CameraService.deleteVideoFile(cameraId, node.fullPath);
                            // Sau khi server xoá xong, remove node khỏi tree
                            TreeItem<VideoNode> parent = getTreeItem().getParent();
                            parent.getChildren().remove(getTreeItem());
                            if (parent.getChildren().isEmpty()) {
                                parent.getParent().getChildren().remove(parent);
                            }
                        } catch (Exception ex) {
                            ex.printStackTrace();
                            new Alert(Alert.AlertType.ERROR,
                                    "Xoá video lỗi:\n" + ex.getMessage(),
                                    ButtonType.OK).showAndWait();
                        }
                    });
                    setContextMenu(new ContextMenu(del));
                }
            }
        });

        Button btnPlay = new Button();
        btnPlay.setDisable(true);

        HBox controls = new HBox(10, btnPlay);
        controls.setPadding(new Insets(5));

        VBox leftBox = new VBox(10,
                new Label("Videos"),
                tree,
                controls // controls giờ sẽ nằm ngay dưới TreeView
        );
        leftBox.setPadding(new Insets(10));
        leftBox.setPrefWidth(300);

        BorderPane pane = new BorderPane();
        pane.setPadding(new Insets(10));
        pane.setLeft(leftBox);

        // onSelect → play
        tree.getSelectionModel().selectedItemProperty()
                .addListener((o, old, nw) -> {
                    if (nw != null && !nw.getValue().isDir) {
                        playVideo(nw.getValue(), btnPlay);
                    }
                });

        btnPlay.setText("Mở hệ thống");
        btnPlay.setDisable(false);

        btnPlay.setOnAction(e -> {
            TreeItem<VideoNode> sel = tree.getSelectionModel().getSelectedItem();
            if (sel != null && !sel.getValue().isDir) {
                File file = PROJECT_BE.resolve(sel.getValue().fullPath).toFile();
                openInSystemPlayer(file);
            }
        });

        Stage stage = new Stage();
        stage.setTitle("Chi tiết camera: " + cameraId);
        stage.setScene(new Scene(pane, 500, 500));
        stage.show();
    }

    private static TreeItem<VideoNode> buildTree(List<String> raw) {
        Map<String, Map<String, List<VideoNode>>> m = new TreeMap<>(Comparator.reverseOrder());

        for (String p : raw) {
            String[] a = p.split("/");
            if (a.length < 4)
                continue;
            String date = a[1], hour = a[2], fn = a[3];
            m.computeIfAbsent(date, d -> new TreeMap<>(Comparator.reverseOrder()))
                    .computeIfAbsent(hour, h -> new ArrayList<>())
                    .add(new VideoNode(fn, p, false));
        }

        TreeItem<VideoNode> root = new TreeItem<>(new VideoNode("ROOT", null, true));
        m.forEach((date, hm) -> {
            TreeItem<VideoNode> dn = new TreeItem<>(new VideoNode("📅 " + date, null, true));
            hm.forEach((hour, list) -> {
                TreeItem<VideoNode> hn = new TreeItem<>(new VideoNode("⏰ " + hour, null, true));
                list.sort(Comparator.comparing(n -> n.display));
                list.forEach(vn -> hn.getChildren().add(new TreeItem<>(vn)));
                if (!hn.getChildren().isEmpty())
                    dn.getChildren().add(hn);
            });
            if (!dn.getChildren().isEmpty())
                root.getChildren().add(dn);
        });
        return root;
    }

    private static void playVideo(VideoNode node,
            Button btn) {
        VideoNode current;
        current = node;

        // kích hoạt nút hệ thống
        btn.setDisable(false);
        btn.setText("Mở hệ thống");
    }

    private static void generateThumbnail(VideoNode node,
            ImageView iv,
            TreeCell<VideoNode> cell) {
        File f = PROJECT_BE.resolve(node.fullPath).toFile();
        MediaPlayer tmp = new MediaPlayer(new Media(f.toURI().toString()));
        MediaView mv = new MediaView(tmp);

        tmp.setOnReady(() -> tmp.seek(Duration.seconds(0.1)));
        tmp.setOnPlaying(() -> {
            Image img = mv.snapshot(null, null);
            Platform.runLater(() -> {
                iv.setImage(img); // fill ảnh
                cell.setGraphic(iv); // giờ mới show graphic
            });
            tmp.stop();
            tmp.dispose();
        });
        tmp.play();
    }

    private static void deleteVideo(VideoNode node, TreeItem<VideoNode> item) {
        File f = PROJECT_BE.resolve(node.fullPath).toFile();
        if (f.delete()) {
            TreeItem<VideoNode> parent = item.getParent();
            parent.getChildren().remove(item);
            if (parent.getChildren().isEmpty())
                parent.getParent().getChildren().remove(parent);
        } else {
            new Alert(Alert.AlertType.ERROR,
                    "Không xóa được: " + node.display,
                    ButtonType.OK).showAndWait();
        }
    }

    private static class VideoNode {
        final String display;
        final String fullPath;
        final boolean isDir;

        VideoNode(String d, String p, boolean dir) {
            this.display = d;
            this.fullPath = p;
            this.isDir = dir;
        }

        @Override
        public String toString() {
            return display;
        }
    }

    public static void openInSystemPlayer(File file) {
        if (!file.exists()) {
            System.err.println("File không tồn tại: " + file);
            return;
        }
        if (Desktop.isDesktopSupported()) {
            try {
                Desktop.getDesktop().open(file);
            } catch (IOException e) {
                e.printStackTrace();
                // Show alert nếu muốn
            }
        } else {
            System.err.println("Desktop API không được hỗ trợ trên nền tảng này.");
        }
    }
}
