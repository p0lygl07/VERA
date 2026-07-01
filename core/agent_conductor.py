def _handle_socket_client(self, client_socket: socket.socket):
        """Processes incoming runtime instructions with fallback for raw strings."""
        with client_socket:
            try:
                data = client_socket.recv(4096).decode('utf-8').strip()
                if not data:
                    return  # Silent return on empty connection pings
                
                try:
                    payload = json.loads(data)
                    print(f"\n[VERA IPC] Action Payload Received: {payload}")
                except json.JSONDecodeError:
                    # Handle raw strings gracefully (e.g., direct text from simple scripts)
                    print(f"\n[VERA IPC] Raw String Received: {data}")
                    payload = {"origin": "raw_pipe", "action": "execute", "text": data}
                
                # ---- ROUTING MECHANISM TO SUB-AGENTS ----
                target = payload.get("target")
                # Balanced payload extraction to support multiple incoming schemas seamlessly
                task_text = payload.get("text") or payload.get("task") or payload.get("payload")
                
                if target in ["monitor_operative", "sre_engineer"] and task_text:
                    # Dynamic execution via the factory-built smolagents
                    result = self.spawn_and_route(target, task_text)
                    response = {"status": "ACK", "message": "Task completed by sub-agent", "result": str(result)}
                else:
                    # Default handling / global fallback routing
                    response = {"status": "ACK", "message": "Data processed successfully"}
                
                client_socket.sendall(json.dumps(response).encode('utf-8'))
            except Exception as e:
                print(f"[VERA IPC] Socket error: {e}")