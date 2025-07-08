package com.example.frontend.util;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

public class MultipartStreamReader {
    private final InputStream input;
    private final String boundary;

    public MultipartStreamReader(InputStream input, String boundary) {
        this.input = input;
        this.boundary = "--" + boundary;
    }

    public byte[] readNextPart() throws IOException {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] lineBuffer = new byte[1024];
        boolean inContent = false;

        while (true) {
            int len = readLine(lineBuffer);
            if (len == -1) return null;

            String line = new String(lineBuffer, 0, len);

            if (line.startsWith(boundary)) {
                if (inContent) break; // kết thúc ảnh hiện tại
                inContent = true;
                skipHeaders(lineBuffer);
                continue;
            }

            if (inContent) {
                buffer.write(lineBuffer, 0, len);
            }
        }

        return buffer.toByteArray();
    }

    private void skipHeaders(byte[] lineBuffer) throws IOException {
        int len;
        while ((len = readLine(lineBuffer)) != -1) {
            String header = new String(lineBuffer, 0, len).trim();
            if (header.isEmpty()) break; // kết thúc headers
        }
    }

    private int readLine(byte[] buffer) throws IOException {
        int i = 0, b;
        while (i < buffer.length && (b = input.read()) != -1) {
            buffer[i++] = (byte) b;
            if (b == '\n') break;
        }
        return (i == 0) ? -1 : i;
    }
}
