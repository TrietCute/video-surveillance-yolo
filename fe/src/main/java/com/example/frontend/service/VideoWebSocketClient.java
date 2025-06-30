package com.example.frontend.service;

import okhttp3.*;
import okio.ByteString;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

public class VideoWebSocketClient extends WebSocketListener {

    private final OkHttpClient client;
    private WebSocket webSocket;

    private final Consumer<BufferedImage> onFrameReceived;

    public VideoWebSocketClient(Consumer<BufferedImage> onFrameReceived) {
        this.client = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .build();
        this.onFrameReceived = onFrameReceived;
    }

    public void connect(String url) {
        Request request = new Request.Builder().url(url).build();
        webSocket = client.newWebSocket(request, this);
    }

    public void sendFrame(byte[] jpegBytes) {
        if (webSocket != null) {
            webSocket.send(ByteString.of(jpegBytes));
        }
    }

    @Override
    public void onMessage(WebSocket webSocket, ByteString bytes) {
        try {
            ByteArrayInputStream bais = new ByteArrayInputStream(bytes.toByteArray());
            BufferedImage img = ImageIO.read(bais);
            if (img != null) {
                onFrameReceived.accept(img); // gửi về controller hoặc GUI để hiển thị
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    @Override
    public void onFailure(WebSocket webSocket, Throwable t, Response response) {
        System.err.println("❌ WebSocket failed: " + t.getMessage());
    }

    public void close() {
        if (webSocket != null) {
            webSocket.close(1000, "Client closing");
        }
    }
}
