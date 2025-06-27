package com.example.frontend.service;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.json.JSONArray;
import org.json.JSONObject;

import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class CameraService {
        private static final OkHttpClient client = new OkHttpClient();
        private static final String BASE_URL = "http://localhost:8000";

        private CameraService() {
                // Ngăn tạo instance
        }

        public static List<Map<String, String>> fetchCameraList() throws IOException {
                Request request = new Request.Builder()
                                .url(BASE_URL + "/cameras")
                                .build();

                try (Response response = client.newCall(request).execute()) {
                        String json = response.body().string();
                        JSONArray array = new JSONArray(json);

                        List<Map<String, String>> result = new ArrayList<>();
                        for (int i = 0; i < array.length(); i++) {
                                JSONObject obj = array.getJSONObject(i);

                                String id = obj.optString("id", "");
                                String url = obj.optString("url", "");

                                // Bỏ qua nếu thiếu id hoặc url
                                if (!id.isEmpty() && !url.isEmpty()) {
                                        result.add(Map.of("id", id, "url", url));
                                }
                        }

                        return result;
                }
        }

        public static void addCamera(String url) throws IOException {
                RequestBody body = RequestBody.create(
                                MediaType.parse("application/json"),
                                "{\"url\": \"" + url + "\"}");
                Request request = new Request.Builder()
                                .url(BASE_URL + "/add-camera")
                                .post(body)
                                .build();
                client.newCall(request).execute().close();
        }

        public static void startStream(String url) throws IOException {
                HttpUrl.Builder urlBuilder = HttpUrl.parse(BASE_URL + "/start-stream").newBuilder();
                urlBuilder.addQueryParameter("url", url);

                Request request = new Request.Builder()
                                .url(urlBuilder.build())
                                .get()
                                .build();
                client.newCall(request).execute().close();
        }

        public static void deleteCamera(String url) throws IOException {
                RequestBody body = RequestBody.create(
                                MediaType.parse("application/json"),
                                "{\"url\": \"" + url + "\"}");
                Request request = new Request.Builder()
                                .url(BASE_URL + "/delete-camera")
                                .delete(body)
                                .build();
                client.newCall(request).execute().close();
        }

        public static void stopStream(String url) throws IOException {
                HttpUrl.Builder urlBuilder = HttpUrl.parse(BASE_URL + "/stop-stream").newBuilder();
                urlBuilder.addQueryParameter("url", url);

                Request request = new Request.Builder()
                                .url(urlBuilder.build())
                                .get()
                                .build();
                client.newCall(request).execute().close();
        }

        public static List<String> getCameraFiles(String cameraId) throws IOException {
                HttpUrl.Builder urlBuilder = HttpUrl.parse(BASE_URL + "/camera-files").newBuilder();
                urlBuilder.addQueryParameter("camera_id", cameraId);

                Request request = new Request.Builder()
                                .url(urlBuilder.build())
                                .get()
                                .build();

                try (Response response = client.newCall(request).execute()) {
                        if (!response.isSuccessful())
                                throw new IOException("Unexpected code " + response);
                        String json = response.body().string();
                        JSONObject jsonObject = new JSONObject(json);
                        JSONArray videoArray = jsonObject.getJSONArray("videos");

                        List<String> videoPaths = new ArrayList<>();
                        for (int i = 0; i < videoArray.length(); i++) {
                                String path = videoArray.getString(i).replace("\\", "/");
                                videoPaths.add(path);
                        }
                        return videoPaths;
                }
        }

        public static void deleteVideoFile(String cameraId, String videoPath) throws IOException {
                HttpUrl url = HttpUrl.parse(BASE_URL + "/camera-files").newBuilder()
                                .addQueryParameter("camera_id", cameraId)
                                .addQueryParameter("video_path", videoPath)
                                .build();
                Request request = new Request.Builder()
                                .url(url)
                                .delete()
                                .build();
                try (Response response = client.newCall(request).execute()) {
                        if (!response.isSuccessful()) {
                                throw new IOException("Delete failed: " + response);
                        }
                }
        }
}
