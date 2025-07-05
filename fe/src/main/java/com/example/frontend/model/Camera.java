package com.example.frontend.model;

import com.fasterxml.jackson.annotation.JsonProperty;

public class Camera {
    private String id;
    private String url;
    private String status;
    @JsonProperty("room_id")
    private String roomId;

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getUrl() { return url; }
    public void setUrl(String url) { this.url = url; }
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
    public String getRoomId() { return roomId; }
    public void setRoomId(String roomId) { this.roomId = roomId; }
}
