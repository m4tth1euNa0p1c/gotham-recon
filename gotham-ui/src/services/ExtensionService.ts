import { useUIStore } from "@/stores/uiStore";

// Message types
export type ExtensionMessage =
    | { type: "GOTHAM_PING" }
    | { type: "GOTHAM_PONG"; version: string }
    | { type: "GOTHAM_SCAN_TARGET"; target: string }
    | { type: "GOTHAM_EXT_LOG"; message: string; level: string };

class ExtensionService {
    private static instance: ExtensionService;
    private checkInterval: NodeJS.Timeout | null = null;

    private constructor() {
        if (typeof window !== "undefined") {
            window.addEventListener("message", this.handleMessage);
            this.startConnectionCheck();
        }
    }

    public static getInstance(): ExtensionService {
        if (!ExtensionService.instance) {
            ExtensionService.instance = new ExtensionService();
        }
        return ExtensionService.instance;
    }

    private handleMessage = (event: MessageEvent) => {
        // Basic security check - in prod, verify origin
        if (!event.data || typeof event.data !== "object") return;

        // Check for our specific protocol prefix or structure
        // Assuming messages from extension might not have a strict prefix but follow the type
        const { type } = event.data;

        if (type === "GOTHAM_PONG") {
            useUIStore.getState().setExtensionConnected(true);
            console.log("[Extension] Connected:", event.data.version);
        } else if (type === "GOTHAM_EXT_DISCONNECTED") {
            useUIStore.getState().setExtensionConnected(false);
        }
    };

    private startConnectionCheck() {
        // Ping extension every 5 seconds to check if it's alive
        this.checkInterval = setInterval(() => {
            this.sendMessage({ type: "GOTHAM_PING" });

            // Auto-set to false if we don't get a pong in a while?
            // For now, let's keep it simple. If we postMessage, we rely on PONG to set true.
            // A more robust way would be to set false here, and let PONG set true.
            // But user experience might flicker. 
        }, 5000);

        // Initial ping
        setTimeout(() => this.sendMessage({ type: "GOTHAM_PING" }), 1000);
    }

    public sendMessage(message: ExtensionMessage) {
        if (typeof window !== "undefined") {
            // Send to content script via window.postMessage
            // Content script should listen to window messages and relay to background
            window.postMessage({ ...message, source: "GOTHAM_UI" }, "*");
        }
    }

    public startScan(target: string) {
        this.sendMessage({ type: "GOTHAM_SCAN_TARGET", target });
    }
}

export const extensionService = ExtensionService.getInstance();
