// 1. Imports and API response type
import { useEffect, useState } from 'react';
import { Alert, Anchor, Button, Group, ScrollArea, Select, Stack, Table, Text, TextInput, Title } from '@mantine/core';
import PaymentForm from '../components/PaymentForm';
import { money } from './invoiceData';

type Payment = {
  id: number; payment_date: string; invoice_id: number; invoice_number: string;
  supplier: string; currency: string; amount: string; base_amount: string;
  bank_fee: string; bank_total: string; reference: string | null;
};

export default function Payments({ onOpenInvoice }: { onOpenInvoice: (id: number) => void }) {
  // 2. State
  const [payments, setPayments] = useState<Payment[] | null>(null);
  const [error, setError] = useState('');
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState('');
  const [currency, setCurrency] = useState<string | null>('All currencies');

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadPayments() {
      try {
        const response = await fetch('/api/payments');
        if (!response.ok) throw new Error(`Could not load payments (${response.status}).`);
        const data: Payment[] = await response.json();
        if (active) setPayments(data);
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load payments.');
      }
    }
    loadPayments();
    return () => { active = false; };
  }, []);

  // 4. Filtering
  const query = search.trim().toLowerCase();
  const rows = (payments ?? []).filter((row) =>
    `${row.supplier} ${row.invoice_number} ${row.reference ?? ''}`.toLowerCase().includes(query) &&
    (currency === 'All currencies' || row.currency === currency),
  );

  // 5. View
  if (adding) return <PaymentForm onBack={() => setAdding(false)} onCreated={onOpenInvoice} />;
  return (
    <Stack gap="lg">
      <Group justify="space-between"><Title order={1} size="h2">Payments</Title><Button onClick={() => setAdding(true)}>+ Add payment</Button></Group>
      <Group align="end">
        <TextInput label="Search payments" placeholder="Supplier, invoice number or reference" value={search} onChange={(event) => setSearch(event.currentTarget.value)} style={{ flex: 1 }} miw={200} />
        <Select label="Currency" data={['All currencies', 'GBP', 'EUR', 'USD']} value={currency} onChange={setCurrency} allowDeselect={false} w={180} />
      </Group>
      {error ? <Alert color="red" title="Payments unavailable">{error} Refresh to retry.</Alert> : !payments ? <Text role="status">Loading payments…</Text> : (
        <>
          <ScrollArea>
            <Table highlightOnHover miw={1000} verticalSpacing="sm">
              <Table.Thead><Table.Tr>{['Date', 'Payment', 'Supplier', 'Invoice', 'Reference', 'CCY'].map((label) => <Table.Th key={label}>{label}</Table.Th>)}{['Amount', 'Settlement GBP', 'Fees GBP', 'Bank total GBP'].map((label) => <Table.Th key={label} ta="right">{label}</Table.Th>)}</Table.Tr></Table.Thead>
              <Table.Tbody>{rows.map((row) => (
                <Table.Tr key={row.id} onClick={() => onOpenInvoice(row.invoice_id)} style={{ cursor: 'pointer' }}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{row.payment_date}</Table.Td><Table.Td>#{row.id}</Table.Td><Table.Td>{row.supplier}</Table.Td>
                  <Table.Td><Anchor component="button" size="sm" onClick={(event) => { event.stopPropagation(); onOpenInvoice(row.invoice_id); }}>{row.invoice_number}</Anchor></Table.Td>
                  <Table.Td>{row.reference || '—'}</Table.Td><Table.Td>{row.currency}</Table.Td>
                  <Table.Td ta="right">{money(row.amount)}</Table.Td><Table.Td ta="right">{money(row.base_amount)}</Table.Td><Table.Td ta="right">{money(row.bank_fee)}</Table.Td><Table.Td ta="right">{money(row.bank_total)}</Table.Td>
                </Table.Tr>
              ))}</Table.Tbody>
            </Table>
          </ScrollArea>
          {rows.length === 0 && <Text c="dimmed">{payments.length === 0 ? 'No payments recorded yet.' : 'No payments match these filters.'}</Text>}
          <Text size="xs" c="dimmed">Select a payment to open its invoice. Settlement excludes bank fees.</Text>
        </>
      )}
    </Stack>
  );
}
