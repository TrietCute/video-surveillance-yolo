// src/main/java/com/example/frontend/service/ApiService.java
package com.example.frontend.service;

import com.example.frontend.model.Camera;
import com.example.frontend.model.Room;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import okhttp3.*; // <-- Import OkHttp

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

public class ApiService {
    private static final String BASE_URL = "http://localhost:8000";
    // Thay thế HttpClient bằng OkHttpClient
    private final OkHttpClient client = new OkHttpClient();
    private final ObjectMapper mapper = new ObjectMapper();
    public static final MediaType JSON = MediaType.get("application/json; charset=utf-8");

    public List<Room> getRooms() throws IOException {
        Request request = new Request.Builder()
                .url(BASE_URL + "/rooms")
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) throw new IOException("Lỗi không mong muốn: " + response);
            return mapper.readValue(Objects.requireNonNull(response.body()).string(), new TypeReference<>() {});
        }
    }

    public Room addRoom(String name) throws IOException {
        // Sử dụng OkHttp để tạo request
        String jsonPayload = mapper.writeValueAsString(java.util.Map.of("name", name));
        RequestBody body = RequestBody.create(jsonPayload, JSON);
        Request request = new Request.Builder()
                .url(BASE_URL + "/rooms")
                .post(body)
                .build();

        try (Response response = client.newCall(request).execute()) {
            String responseBody = Objects.requireNonNull(response.body()).string();
            if (!response.isSuccessful()) {
                // Ném ra lỗi để Controller có thể bắt và hiển thị
                throw new IOException("Server trả về lỗi: " + response.code() + " - " + responseBody);
            }
            return mapper.readValue(responseBody, Room.class);
        }
    }

    public Room updateRoom(String roomId, String newName) throws IOException {
        String jsonPayload = mapper.writeValueAsString(java.util.Map.of("name", newName));
        RequestBody body = RequestBody.create(jsonPayload, JSON);
        Request request = new Request.Builder()
                .url(BASE_URL + "/rooms/" + roomId)
                .put(body) // Sử dụng .put() cho yêu cầu UPDATE
                .build();

        try (Response response = client.newCall(request).execute()) {
            String responseBody = Objects.requireNonNull(response.body()).string();
            if (!response.isSuccessful()) {
                throw new IOException("Server trả về lỗi: " + response.code() + " - " + responseBody);
            }
            return mapper.readValue(responseBody, Room.class);
        }
    }

    public void deleteRoom(String roomId) throws IOException {
        Request request = new Request.Builder()
                .url(BASE_URL + "/rooms/" + roomId)
                .delete()
                .build();

        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Server trả về lỗi: " + response.code() + " - " + response.body().string());
            }
        }
    }

    public List<Camera> getCamerasInRoom(String roomId) throws IOException {
        Request request = new Request.Builder()
                .url(BASE_URL + "/cameras")
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) throw new IOException("Lỗi không mong muốn: " + response);

            List<Camera> allCameras = mapper.readValue(Objects.requireNonNull(response.body()).string(), new TypeReference<>() {});
            return allCameras.stream()
                    .filter(camera -> roomId.equals(camera.getRoomId()))
                    .collect(Collectors.toList());
        }
    }

    public Camera addCameraToRoom(String roomId, String url) throws IOException {
        String jsonPayload = mapper.writeValueAsString(java.util.Map.of("url", url, "room_id", roomId));
        RequestBody body = RequestBody.create(jsonPayload, JSON);
        Request request = new Request.Builder()
                .url(BASE_URL + "/add-camera")
                .post(body)
                .build();
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) throw new IOException("Lỗi không mong muốn: " + response);
            return mapper.readValue(Objects.requireNonNull(response.body()).string(), Camera.class);
        }
    }
    
    public void deleteCamera(String cameraUrl) throws IOException {
        // Tạo body JSON chứa url của camera
        String jsonPayload = mapper.writeValueAsString(java.util.Map.of("url", cameraUrl));
        RequestBody body = RequestBody.create(jsonPayload, JSON);

        // Gửi yêu cầu DELETE đến endpoint /delete-camera với body đã tạo
        Request request = new Request.Builder()
                .url(BASE_URL + "/delete-camera")
                .delete(body)
                .build();
                
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) {
                throw new IOException("Server trả về lỗi: " + response.code() + " - " + Objects.requireNonNull(response.body()).string());
            }
        }
    }

    public Camera updateCameraUrl(String cameraId, String newUrl) throws IOException {
        String jsonPayload = mapper.writeValueAsString(java.util.Map.of("url", newUrl));
        RequestBody body = RequestBody.create(jsonPayload, JSON);
        Request request = new Request.Builder()
                .url(BASE_URL + "/cameras/" + cameraId)
                .put(body)
                .build();
        try (Response response = client.newCall(request).execute()) {
            String responseBody = Objects.requireNonNull(response.body()).string();
            if (!response.isSuccessful()) {
                throw new IOException("Server trả về lỗi: " + response.code() + " - " + responseBody);
            }
            return mapper.readValue(responseBody, Camera.class);
        }
    }

    public List<String> getEventVideos(String cameraId) throws IOException {
        // Xây dựng URL với query parameter
        HttpUrl url = Objects.requireNonNull(HttpUrl.parse(BASE_URL + "/camera-files")).newBuilder()
            .addQueryParameter("camera_id", cameraId)
            .build();
            
        Request request = new Request.Builder().url(url).build();
        
        try (Response response = client.newCall(request).execute()) {
            if (!response.isSuccessful()) throw new IOException("Lỗi không mong muốn: " + response);

            JsonNode rootNode = mapper.readTree(Objects.requireNonNull(response.body()).string());
            JsonNode videosNode = rootNode.path("videos");
            List<String> videoPaths = new ArrayList<>();
            if (videosNode.isArray()) {
                for (JsonNode pathNode : videosNode) {
                    videoPaths.add(pathNode.asText());
                }
            }
            return videoPaths;
        }
    }
}