"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useCvChat } from "../hooks/useCvChat";

interface CvChatWidgetProps {
  documentId: string;
  onComplete?: () => void;
}

export function CvChatWidget({ documentId, onComplete }: CvChatWidgetProps) {
  const { session, start, sendMessage } = useCvChat(documentId);
  const [input, setInput] = useState("");

  if (!session) {
    return (
      <Button onClick={() => start.mutate()} disabled={start.isPending}>
        {start.isPending ? "Starting..." : "Start CV completeness chat"}
      </Button>
    );
  }

  function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    sendMessage.mutate(input, {
      onSuccess: (updated) => {
        setInput("");
        if (updated.status === "completed") onComplete?.();
      },
    });
  }

  return (
    <div className="flex h-96 flex-col rounded-lg border">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {session.messages.map((message) => (
          <div
            key={message.id}
            className={message.role === "assistant" ? "text-left" : "text-right"}
          >
            <span
              className={
                message.role === "assistant"
                  ? "inline-block rounded-lg bg-muted px-3 py-2 text-sm"
                  : "inline-block rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground"
              }
            >
              {message.content}
            </span>
          </div>
        ))}
      </div>
      {session.status === "active" ? (
        <form onSubmit={handleSend} className="flex gap-2 border-t p-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your answer..."
            disabled={sendMessage.isPending}
          />
          <Button type="submit" disabled={sendMessage.isPending || !input.trim()}>
            Send
          </Button>
        </form>
      ) : (
        <div className="border-t p-3 text-center text-sm text-muted-foreground">
          {session.status === "completed" ? "All done — your CV is up to date." : "Chat ended."}
        </div>
      )}
    </div>
  );
}
