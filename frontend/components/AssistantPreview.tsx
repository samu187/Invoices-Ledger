// 1. Imports
import { useEffect, useState } from 'react';
import { ActionIcon, Box, CloseButton, Group, Paper, Portal, ScrollArea, Stack, Text, TextInput, UnstyledButton } from '@mantine/core';

export function BotIcon({ width = 52, height = 56 }: { width?: number; height?: number }) {
  return (
    <svg className="bookkeeper-bot" width={width} height={height} viewBox="0 0 64 68" fill="none" aria-hidden="true">
      <path d="M32 12V6" stroke="#6372c8" strokeWidth="3" strokeLinecap="round" />
      <circle cx="32" cy="5" r="3" fill="#9a8dde" />
      <rect x="11" y="13" width="42" height="31" rx="11" fill="#e1e6ff" stroke="#6372c8" strokeWidth="2" />
      <rect x="5" y="24" width="6" height="12" rx="3" fill="#9a8dde" />
      <rect x="53" y="24" width="6" height="12" rx="3" fill="#9a8dde" />
      <g className="bookkeeper-eyes"><circle cx="23" cy="27" r="3" fill="#394780" /><circle cx="41" cy="27" r="3" fill="#394780" /></g>
      <path d="M27 35Q32 39 37 35" stroke="#6372c8" strokeWidth="2" strokeLinecap="round" />
      <rect x="11" y="42" width="42" height="20" rx="3" fill="#e3e6ec" stroke="#8792aa" strokeWidth="1.5" />
      <circle cx="32" cy="52" r="3" fill="#b4bdcd" />
      <path d="M14 62H50" stroke="#8792aa" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function AssistantPreview({ opened, onOpenedChange }: { opened: boolean; onOpenedChange: (opened: boolean) => void }) {
  // 2. State
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; text: string }[]>([]);

  // 3. Effects
  useEffect(() => {
    if (!opened) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      onOpenedChange(false);
    }
    window.addEventListener('keydown', closeOnEscape, true);
    return () => window.removeEventListener('keydown', closeOnEscape, true);
  }, [opened, onOpenedChange]);

  // 4. Helpers: local preview only
  function sendMessage(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim()) return;
    setMessages((previous) => [...previous, { role: 'user', text: draft.trim() }, {
      role: 'assistant',
      text: 'This is a preview reply. The assistant is not connected yet, so no records have been created. Once connected, you’ll be able to ask me to record invoices, payments and suppliers.',
    }]);
    setDraft('');
  }

  // 5. View
  return (
    <>
      <UnstyledButton className="bookkeeper-launcher" onClick={() => onOpenedChange(!opened)} aria-expanded={opened} aria-controls="bookkeeper-chat">
        <Group gap="sm" wrap="nowrap">
          <BotIcon />
          <div><Text size="sm" fw={600}>Bookkeeping assistant</Text><Text size="xs" c="dimmed">AI Bot Coming soon!</Text></div>
        </Group>
      </UnstyledButton>
      {opened && (
        <Portal>
        <Paper id="bookkeeper-chat" className="bookkeeper-chat" component="section" aria-label="Bookkeeping assistant chat" withBorder radius="lg" shadow="lg" p="md">
          <Stack gap="sm">
            <Group justify="space-between">
              <div><Text size="sm" fw={600}>Bookkeeping assistant</Text><Text size="xs" c="dimmed">Local preview · Not connected to AI</Text></div>
              <CloseButton aria-label="Close assistant" onClick={() => onOpenedChange(false)} />
            </Group>
            {messages.length === 0 ? <Text size="sm" c="dimmed">What would you like to record? Try “Add a supplier called River Studio”.</Text> : (
              <ScrollArea.Autosize mah={230} viewportRef={(element) => { if (element) element.scrollTop = element.scrollHeight; }}>
                <Stack gap="sm" role="log" aria-live="polite" aria-label="Chat messages">
                  {messages.map((message, index) => (
                    <Box key={index} p="sm" bg={message.role === 'user' ? 'indigo.0' : 'gray.0'} style={{ borderRadius: 10, overflowWrap: 'anywhere' }}>
                      <Text size="xs" fw={600} mb={3}>{message.role === 'user' ? 'You' : 'Assistant · Preview reply'}</Text>
                      <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{message.text}</Text>
                    </Box>
                  ))}
                </Stack>
              </ScrollArea.Autosize>
            )}
            <form onSubmit={sendMessage}>
              <Group gap="xs" wrap="nowrap">
                <TextInput autoFocus aria-label="Message the bookkeeping assistant" placeholder="Ask your bookkeeping assistant…" value={draft} onChange={(event) => setDraft(event.currentTarget.value)} style={{ flex: 1 }} radius="md" />
                <ActionIcon type="submit" size="lg" radius="md" disabled={!draft.trim()} aria-label="Send message">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6" /></svg>
                </ActionIcon>
              </Group>
            </form>
          </Stack>
        </Paper>
        </Portal>
      )}
    </>
  );
}
