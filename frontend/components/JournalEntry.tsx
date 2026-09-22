// 1. Imports and API response type
import { useEffect, useState } from 'react';
import { Alert, Anchor, Group, ScrollArea, Stack, Table, Text, Title } from '@mantine/core';

type Journal = {
  id: number;
  posting_date: string;
  kind: string;
  description: string;
  invoice_id: number | null;
  payment_id: number | null;
  lines: { code: string; name: string; debit: string; credit: string }[];
  total_debit: string;
  total_credit: string;
};

export default function JournalEntry({ id, accountCode, onSelectAccount, onOpenInvoice }: {
  id: number;
  accountCode: string;
  onSelectAccount: (code: string) => void;
  onOpenInvoice: (id: number) => void;
}) {
  // 2. State
  const [journal, setJournal] = useState<Journal | null>(null);
  const [error, setError] = useState('');

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadJournal() {
      try {
        const response = await fetch(`/api/journals/${id}`);
        if (!response.ok) throw new Error(`Could not load journal ${id} (${response.status}).`);
        const data: Journal = await response.json();
        if (active) setJournal(data);
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load journal.');
      }
    }
    loadJournal();
    return () => { active = false; };
  }, [id]);

  // 4. Display helper: preserve the API's decimal amounts
  function money(value: string) {
    const [whole, fraction = ''] = value.split('.');
    return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
  }

  // 5. View
  if (error) return <Alert color="red" title="Journal unavailable">{error} Go back and select the transaction to retry.</Alert>;
  if (!journal) return <Text role="status">Loading journal {id}…</Text>;

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Title order={3} size="h4">Journal #{journal.id}</Title>
        <Text size="sm" c="dimmed">{journal.posting_date} · {journal.kind} · GBP</Text>
      </Group>
      <Text>{journal.description}</Text>
      {(journal.invoice_id !== null || journal.payment_id !== null) && (
        <Text size="sm" c="dimmed">
          {journal.invoice_id !== null && <Anchor component="button" size="sm" onClick={() => onOpenInvoice(journal.invoice_id!)}>Invoice #{journal.invoice_id}</Anchor>}
          {journal.invoice_id !== null && journal.payment_id !== null && ' · '}
          {journal.payment_id !== null && `Payment #${journal.payment_id}`}
        </Text>
      )}
      <ScrollArea.Autosize mah={360}>
        <Table highlightOnHover stickyHeader miw={560} style={{ fontVariantNumeric: 'tabular-nums' }}>
          <Table.Thead><Table.Tr><Table.Th>Code</Table.Th><Table.Th>Account</Table.Th><Table.Th ta="right">Debit</Table.Th><Table.Th ta="right">Credit</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {journal.lines.map((line, index) => (
              <Table.Tr key={index} bg={line.code === accountCode ? '#edf1f6' : undefined} onClick={() => onSelectAccount(line.code)} style={{ cursor: 'pointer' }}>
                <Table.Td>
                  <Anchor component="button" size="sm" aria-label={`Open ledger for account ${line.code}`} onClick={(event) => { event.stopPropagation(); onSelectAccount(line.code); }}>
                    {line.code}
                  </Anchor>
                </Table.Td><Table.Td>{line.name}</Table.Td>
                <Table.Td ta="right">{money(line.debit)}</Table.Td><Table.Td ta="right">{money(line.credit)}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
          <Table.Tfoot><Table.Tr><Table.Th colSpan={2}>Total</Table.Th><Table.Th ta="right">{money(journal.total_debit)}</Table.Th><Table.Th ta="right">{money(journal.total_credit)}</Table.Th></Table.Tr></Table.Tfoot>
        </Table>
      </ScrollArea.Autosize>
      {journal.lines.length === 0 && <Text c="dimmed">This journal has no lines.</Text>}
    </Stack>
  );
}
