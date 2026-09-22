// 1. Imports and API response type
import { useEffect, useState } from 'react';
import { Alert, Anchor, Button, Group, Paper, ScrollArea, SimpleGrid, Stack, Table, Text, Title } from '@mantine/core';
import { MonthPickerInput } from '@mantine/dates';

type VatMonth = {
  month: string; start_date: string; end_date: string;
  code: string; name: string; account_type: string;
  opening_balance: string; debits: string; credits: string;
  net_movement: string; closing_balance: string;
  transactions: {
    entry_id: number; posting_date: string; description: string;
    invoice_id: number | null; payment_id: number | null;
    debit: string; credit: string; balance: string;
  }[];
};

export default function Vat({ month, onMonthChange, onOpenJournal }: {
  month: string;
  onMonthChange: (month: string) => void;
  onOpenJournal: (id: number) => void;
}) {
  // 2. State
  const [report, setReport] = useState<VatMonth | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const validMonth = /^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(month);

  // 3. Effects: discard old responses when the selected month changes
  useEffect(() => {
    let active = true;
    setReport(null);
    setError('');
    if (!validMonth) return;
    async function loadMonth() {
      try {
        const response = await fetch(`/api/accounts/input-vat?month=${encodeURIComponent(month)}`);
        if (!response.ok) throw new Error(`Could not load monthly input VAT (${response.status}).`);
        const data: VatMonth = await response.json();
        if (active) setReport(data);
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load monthly input VAT.');
      }
    }
    loadMonth();
    return () => { active = false; };
  }, [month, validMonth, retry]);

  // 4. Display helpers: keep decimal precision; totals come from the API
  function money(value: string) {
    const [whole, fraction = ''] = value.split('.');
    return `${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
  }

  function balance(value: string) {
    if (/^-?0(?:\.0+)?$/.test(value)) return '0.00';
    return `${money(value.replace(/^-/, ''))} ${value.startsWith('-') ? 'Cr' : 'Dr'}`;
  }

  // 5. View
  return (
    <Stack gap="lg">
      <Group justify="space-between" align="start">
        <div>
          <Title order={1} size="h2">VAT</Title>
          <Text size="sm" c="dimmed">Monthly input VAT · Account 1100 · GBP</Text>
        </div>
        <MonthPickerInput label="Month" placeholder="Choose a month" value={validMonth ? `${month}-01` : null} onChange={(value) => { if (value) onMonthChange(value.slice(0, 7)); }} w={220} />
      </Group>
      {!validMonth ? <Text c="dimmed">Select a month to view input VAT.</Text> : error ? (
        <Alert color="red" title="Input VAT unavailable">
          <Text size="sm">{error}</Text>
          <Button variant="subtle" size="xs" mt="xs" onClick={() => setRetry(retry + 1)}>Retry</Button>
        </Alert>
      ) : !report || report.month !== month ? <Text role="status">Loading input VAT…</Text> : (
        <>
          <Text size="sm" c="dimmed">{report.start_date} to {report.end_date}</Text>
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            {[
              ['Opening balance', balance(report.opening_balance)],
              ['Net movement this month', money(report.net_movement)],
              ['Closing balance', balance(report.closing_balance)],
            ].map(([label, amount]) => (
              <Paper key={label} withBorder radius="md" p="lg">
                <Text size="sm" c="dimmed">{label}</Text>
                <Text size="xl" fw={600} mt="xs" style={{ fontVariantNumeric: 'tabular-nums' }}>GBP {amount}</Text>
              </Paper>
            ))}
          </SimpleGrid>
          <Group justify="space-between">
            <Title order={2} size="md" c="dimmed">— Input VAT ledger —</Title>
            <Text size="sm" c="dimmed">{report.transactions.length} movements</Text>
          </Group>
          <ScrollArea>
            <Table highlightOnHover miw={850}>
              <Table.Thead><Table.Tr><Table.Th>Date</Table.Th><Table.Th>Journal</Table.Th><Table.Th>Description</Table.Th><Table.Th>Source</Table.Th><Table.Th ta="right">Debit GBP</Table.Th><Table.Th ta="right">Credit GBP</Table.Th><Table.Th ta="right">Balance GBP</Table.Th></Table.Tr></Table.Thead>
              <Table.Tbody>
                {report.transactions.map((row, index) => (
                  <Table.Tr key={`${row.entry_id}-${index}`} onClick={() => onOpenJournal(row.entry_id)} style={{ cursor: 'pointer' }}>
                    <Table.Td style={{ whiteSpace: 'nowrap' }}>{row.posting_date}</Table.Td>
                    <Table.Td><Anchor component="button" size="sm" aria-label={`Open journal ${row.entry_id} in Accounts`} onClick={(event) => { event.stopPropagation(); onOpenJournal(row.entry_id); }}>#{row.entry_id}</Anchor></Table.Td>
                    <Table.Td>{row.description}</Table.Td>
                    <Table.Td>{[row.invoice_id !== null && `Invoice #${row.invoice_id}`, row.payment_id !== null && `Payment #${row.payment_id}`].filter(Boolean).join(' · ') || '—'}</Table.Td>
                    <Table.Td ta="right">{money(row.debit)}</Table.Td><Table.Td ta="right">{money(row.credit)}</Table.Td><Table.Td ta="right" style={{ whiteSpace: 'nowrap' }}>{balance(row.balance)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
              <Table.Tfoot><Table.Tr><Table.Th colSpan={4}>Month totals / closing balance</Table.Th><Table.Th ta="right">{money(report.debits)}</Table.Th><Table.Th ta="right">{money(report.credits)}</Table.Th><Table.Th ta="right">{balance(report.closing_balance)}</Table.Th></Table.Tr></Table.Tfoot>
            </Table>
          </ScrollArea>
          {report.transactions.length === 0 && <Text c="dimmed">No input VAT movements in this month. Any opening balance is carried forward.</Text>}
          <Text size="xs" c="dimmed">Select a movement to open its journal in Accounts. This report covers input VAT only, not a VAT return.</Text>
        </>
      )}
    </Stack>
  );
}
