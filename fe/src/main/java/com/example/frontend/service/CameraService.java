package com.example.frontend.service;

import java.io.IOException;
import java.util.List;
import java.util.Map;

import okhttp3.HttpUrl;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

import org.json.JSONArray;

public class CameraService {
        private static final OkHttpClient client = new OkHttpClient();
        private static final String BASE_URL = "http://localhost:8000";

        public static List<String> fetchCameraList() throws IOException {
                Request request = new Request.Builder()
                                .url(BASE_URL + "/cameras")
                                .build();

                try (Response response = client.newCall(request).execute()) {
                        String json = response.body().string();
                        JSONArray array = new JSONArray(json);

                        return array.toList().stream()
                                        .map(obj -> (Map<?, ?>) obj)
                                        .map(map -> map.get("url").toString())
                                        .toList();
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
}
