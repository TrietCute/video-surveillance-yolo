// CameraService.java
package com.example.frontend.service;

import java.io.File;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.bytedeco.javacpp.BytePointer;
import org.json.JSONArray;
import org.json.JSONObject;
import okhttp3.*;
import org.bytedeco.opencv.opencv_core.Mat;
import org.bytedeco.opencv.opencv_videoio.VideoCapture;
import static org.bytedeco.opencv.global.opencv_imgcodecs.imencode;


public class CameraService {
        private static final OkHttpClient client = new OkHttpClient();
        private static final String BASE_URL = "http://localhost:8000";

        public static List<Map<String, String>> fetchCameraList() throws IOException {
                Request request = new Request.Builder().url(BASE_URL + "/cameras").build();
                try (Response response = client.newCall(request).execute()) {
                        String json = response.body().string();
                        JSONArray array = new JSONArray(json);
                        List<Map<String, String>> result = new ArrayList<>();
                        for (int i = 0; i < array.length(); i++) {
                                JSONObject obj = array.getJSONObject(i);
                                String id = obj.optString("id", "");
                                String url = obj.optString("url", "");
                                if (!id.isEmpty() && !url.isEmpty()) {
                                        result.add(Map.of("id", id, "url", url));
                                }
                        }
                        return result;
                }
        }

        public static void addCamera(String url) throws IOException {
                RequestBody body = RequestBody.create(MediaType.parse("application/json"), "{\"url\": \"" + url + "\"}");
                Request request = new Request.Builder().url(BASE_URL + "/add-camera").post(body).build();
                client.newCall(request).execute().close();
        }

        public static void startStream(String url) throws IOException {
                HttpUrl.Builder urlBuilder = HttpUrl.parse(BASE_URL + "/start-stream").newBuilder();
                urlBuilder.addQueryParameter("url", url);
                Request request = new Request.Builder().url(urlBuilder.build()).get().build();
                client.newCall(request).execute().close();
        }

        public static void stopStream(String url) throws IOException {
                HttpUrl.Builder urlBuilder = HttpUrl.parse(BASE_URL + "/stop-stream").newBuilder();
                urlBuilder.addQueryParameter("url", url);
                Request request = new Request.Builder().url(urlBuilder.build()).get().build();
                client.newCall(request).execute().close();
        }

        public static void deleteCamera(String url) throws IOException {
                RequestBody body = RequestBody.create(MediaType.parse("application/json"), "{\"url\": \"" + url + "\"}");
                Request request = new Request.Builder().url(BASE_URL + "/delete-camera").delete(body).build();
                client.newCall(request).execute().close();
        }

        public static List<String> getCameraFiles(String cameraId) throws IOException {
                HttpUrl url = HttpUrl.parse(BASE_URL + "/camera-files").newBuilder()
                        .addQueryParameter("camera_id", cameraId).build();
                Request request = new Request.Builder().url(url).get().build();
                try (Response response = client.newCall(request).execute()) {
                        String json = response.body().string();
                        JSONArray array = new JSONObject(json).getJSONArray("videos");
                        List<String> videoPaths = new ArrayList<>();
                        for (int i = 0; i < array.length(); i++) {
                                videoPaths.add(array.getString(i).replace("\\", "/"));
                        }
                        return videoPaths;
                }
        }

        public static void deleteVideoFile(String cameraId, String videoPath) throws IOException {
                HttpUrl url = HttpUrl.parse(BASE_URL + "/camera-files").newBuilder()
                        .addQueryParameter("camera_id", cameraId)
                        .addQueryParameter("video_path", videoPath).build();
                Request request = new Request.Builder().url(url).delete().build();
                client.newCall(request).execute().close();
        }

        public static void submitTestVideo(File file) throws IOException {
                RequestBody fileBody = RequestBody.create(MediaType.parse("video/mp4"), file);
                MultipartBody requestBody = new MultipartBody.Builder().setType(MultipartBody.FORM)
                        .addFormDataPart("file", file.getName(), fileBody).build();
                Request request = new Request.Builder().url(BASE_URL + "/test-video").post(requestBody).build();
                try (Response response = client.newCall(request).execute()) {
                        if (!response.isSuccessful()) throw new IOException("Test video failed: " + response);
                }

        }
        public static void streamTestVideoRealtime(File videoFile) {
    new Thread(() -> {
        try {
            VideoCapture cap = new VideoCapture(videoFile.getAbsolutePath());
            if (!cap.isOpened()) {
                System.err.println("Không mở được video.");
                return;
            }

            Mat frame = new Mat();
            while (cap.read(frame)) {
                BytePointer buf = new BytePointer();
                imencode(".jpg", frame, buf);

                RequestBody body = RequestBody.create(MediaType.parse("image/jpeg"), buf.getStringBytes());
                Request request = new Request.Builder()
                        .url("http://localhost:8000/process-frame")
                        .post(body)
                        .build();

                try (Response response = client.newCall(request).execute()) {
                    if (!response.isSuccessful()) {
                        System.err.println("Lỗi gửi frame: " + response);
                    }
                }

                // Mô phỏng FPS ~10
                Thread.sleep(100);
            }

            cap.release();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }).start();
}

        
        
}
