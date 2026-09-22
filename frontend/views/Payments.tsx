// 1. Imports and API response type
import { useEffect, useState } from 'react';
import { Alert, Anchor, Button, Group, ScrollArea, Select, Stack, Table, Text, TextInput, Title } from '@mantine/core';
import PaymentForm from '../components/PaymentForm';
import { money } from './invoiceData';

type Payment = {
  id: number; payment_date: string; invoice_id: number; invoice_number: string;
  supplier: string; currency: string; amount: string; exchange_rate: string; base_amount: string;
  bank_fee: string; bank_total: string; reference: string | null;
};

export default function Payments({ onOpenInvoice, onOpenJournal, initialPaymentId }: { onOpenInvoice: (id: number) => void; onOpenJournal: (id: number) => void; initialPaymentId: number | null }) {
  // 2. State
  const [payments, setPayments] = useState<Payment[] | null>(null);
  const [selectedPaymentId, setSelectedPaymentId] = useState<number | null>(initialPaymentId);
  const [paymentDetail, setPaymentDetail] = useState<(Payment & { journal: { id: number } }) | null>(null);
  const [error, setError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [adding, setAdding] = useState(false);
  const [search, setSearch] = useState('');
  const [currency, setCurrency] = useState<string | null>('All currencies');
  const [revision, setRevision] = useState(0);

  // 3. Effects
  useEffect(() => {
    let active = true;
    setError('');
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
  }, [revision]);

  useEffect(() => {
    let active = true;
    if (selectedPaymentId === null) { setPaymentDetail(null); return; }
    setPaymentDetail(null);
    setDetailError('');
    fetch(`/api/payments/${selectedPaymentId}`).then(async (response) => {
      if (!response.ok) throw new Error(`Could not load payment ${selectedPaymentId} (${response.status}).`);
      return response.json();
    }).then((data) => { if (active) setPaymentDetail(data); }).catch((error) => { if (active) setDetailError(error instanceof Error ? error.message : 'Could not load payment.'); });
    return () => { active = false; };
  }, [selectedPaymentId]);

  // 4. Filtering
  const query = search.trim().toLowerCase();
  const rows = (payments ?? []).filter((row) =>
    `${row.supplier} ${row.invoice_number} ${row.reference ?? ''}`.toLowerCase().includes(query) &&
    (currency === 'All currencies' || row.currency === currency),
  );

  // 5. View
  if (selectedPaymentId !== null) return (
    <Stack gap="md">
      <Group justify="space-between"><Title order={1} size="h2">Payment #{selectedPaymentId}</Title><Button variant="default" onClick={() => setSelectedPaymentId(null)}>Back to payments</Button></Group>
      {detailError ? <Alert color="red" title="Payment unavailable">{detailError}</Alert> : !paymentDetail ? <Text role="status">Loading payment…</Text> : (
        <Stack gap="xs">
          <Text>{paymentDetail.payment_date} · {paymentDetail.supplier}</Text>
          <Text>Invoice <Anchor component="button" onClick={() => onOpenInvoice(paymentDetail.invoice_id)}>{paymentDetail.invoice_number} (#{paymentDetail.invoice_id})</Anchor></Text>
          <Text>{paymentDetail.currency} {money(paymentDetail.amount)} · FX rate {paymentDetail.exchange_rate} GBP/{paymentDetail.currency}</Text>
          <Text>GBP settlement {money(paymentDetail.base_amount)} · Fees {money(paymentDetail.bank_fee)} · Bank total {money(paymentDetail.bank_total)}</Text>
          <Group justify="flex-end"><Anchor component="button" size="sm" onClick={() => onOpenJournal(paymentDetail.journal.id)}>Open payment journal ↗</Anchor></Group>
        </Stack>
      )}
    </Stack>
  );
  if (adding) return <PaymentForm onBack={() => setAdding(false)} onOpenInvoice={onOpenInvoice} onCreated={(id) => { setAdding(false); setSelectedPaymentId(id); setRevision(revision + 1); }} />;
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
              <Table.Thead><Table.Tr>{['Date', 'Payment', 'Supplier', 'Invoice', 'Reference', 'CCY'].map((label) => <Table.Th key={label}>{label}</Table.Th>)}{['Amount', 'FX rate (GBP/CCY)', 'Settlement GBP', 'Fees GBP', 'Bank total GBP'].map((label) => <Table.Th key={label} ta="right">{label}</Table.Th>)}</Table.Tr></Table.Thead>
              <Table.Tbody>{rows.map((row) => (
                <Table.Tr key={row.id} onClick={() => setSelectedPaymentId(row.id)} style={{ cursor: 'pointer' }}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{row.payment_date}</Table.Td><Table.Td><Anchor component="button" size="sm" onClick={(event) => { event.stopPropagation(); setSelectedPaymentId(row.id); }}>#{row.id}</Anchor></Table.Td><Table.Td>{row.supplier}</Table.Td>
                  <Table.Td><Anchor component="button" size="sm" onClick={(event) => { event.stopPropagation(); onOpenInvoice(row.invoice_id); }}>{row.invoice_number}</Anchor></Table.Td>
                  <Table.Td>{row.reference || '—'}</Table.Td><Table.Td>{row.currency}</Table.Td>
                  <Table.Td ta="right">{money(row.amount)}</Table.Td><Table.Td ta="right">{row.exchange_rate}</Table.Td><Table.Td ta="right">{money(row.base_amount)}</Table.Td><Table.Td ta="right">{money(row.bank_fee)}</Table.Td><Table.Td ta="right">{money(row.bank_total)}</Table.Td>
                </Table.Tr>
              ))}</Table.Tbody>
            </Table>
          </ScrollArea>
          {rows.length === 0 && <Text c="dimmed">{payments.length === 0 ? 'No payments recorded yet.' : 'No payments match these filters.'}</Text>}
          <Text size="xs" c="dimmed">Select a payment to view its details, or select an invoice number to open the invoice. FX rate is GBP per unit of payment currency; settlement excludes bank fees.</Text>
        </>
      )}
    </Stack>
  );
}
