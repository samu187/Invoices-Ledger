// 1. Imports
import { useEffect, useRef, useState } from 'react';
import { Alert, Anchor, Button, Group, Paper, Select, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { type Invoice, isZero, money } from '../views/invoiceData';

export default function PaymentForm({ onBack, onCreated, onOpenInvoice }: { onBack: () => void; onCreated: (paymentId: number) => void; onOpenInvoice: (invoiceId: number) => void }) {
  // 2. State
  const today = new Date();
  const todayString = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  const [invoices, setInvoices] = useState<Invoice[] | null>(null);
  const [suppliers, setSuppliers] = useState<{ id: number; name: string }[]>([]);
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);
  const [requestId] = useState(() => crypto.randomUUID());
  const [invoiceId, setInvoiceId] = useState<string | null>(null);
  const [date, setDate] = useState<string | null>(todayString);
  const [amount, setAmount] = useState('');
  const [rate, setRate] = useState('1');
  const [fees, setFees] = useState('0');
  const [reference, setReference] = useState('');
  const invoice = invoices?.find((row) => String(row.id) === invoiceId);

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadInvoices() {
      try {
        const [invoiceResponse, supplierResponse] = await Promise.all([fetch('/api/invoices'), fetch('/api/suppliers')]);
        if (!invoiceResponse.ok || !supplierResponse.ok) throw new Error('Could not load suppliers and outstanding invoices.');
        const [rows, supplierRows]: [Invoice[], { id: number; name: string }[]] = await Promise.all([invoiceResponse.json(), supplierResponse.json()]);
        if (rows.some((row) => !Number.isInteger(row.supplier_id))) throw new Error('Restart FastAPI to enable supplier-specific invoice selection.');
        if (active) {
          setSuppliers(supplierRows);
          setInvoices(rows.filter((row) => row.has_invoice_posting && !isZero(row.balance) && !row.balance.startsWith('-')));
        }
      } catch (error) {
        if (active) setLoadError(error instanceof Error ? error.message : 'Could not load invoices.');
      }
    }
    loadInvoices();
    return () => { active = false; };
  }, []);

  // 4. Helpers
  function selectSupplier(value: string | null) {
    setSupplierId(value);
    selectInvoice(null);
  }

  function selectInvoice(value: string | null) {
    setInvoiceId(value);
    const selected = invoices?.find((row) => String(row.id) === value);
    setAmount('');
    setFees('0');
    setRate(selected?.currency === 'GBP' ? '1' : '');
    setError('');
  }

  function cents(value: string) {
    const [whole, fraction = ''] = value.split('.');
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
  }

  async function recordPayment(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current) return;
    setError('');
    if (!invoice || !date) { setError('Select an invoice and payment date.'); return; }
    if (!/^\d{1,16}(\.\d{1,2})?$/.test(amount) || cents(amount) <= 0n) { setError('Enter a positive payment amount with up to two decimal places.'); return; }
    if (cents(amount) > cents(invoice.balance)) { setError('Payment exceeds the invoice’s outstanding balance.'); return; }
    if (!/^\d{1,16}(\.\d{1,2})?$/.test(fees)) { setError('Bank fees must be zero or positive, with up to two decimal places.'); return; }
    if (!/^\d{1,10}(\.\d{1,10})?$/.test(rate) || /^0+(\.0+)?$/.test(rate)) { setError('Enter a positive exchange rate, in GBP per unit of invoice currency.'); return; }
    if (date < invoice.date || date > todayString) { setError('Payment date must be between the invoice date and today.'); return; }
    submitting.current = true;
    setSaving(true);
    try {
      const response = await fetch('/api/payments', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ invoice_id: invoice.id, currency: invoice.currency, amount, payment_date: date, bank_account_code: '1000', exchange_rate: rate, bank_fees: fees, reference: reference.trim() || null, request_id: requestId }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join(' ') : 'Could not record payment.');
      }
      const result: { payment_id: number } = await response.json();
      onCreated(result.payment_id);
    } catch (error) {
      setError(error instanceof TypeError ? 'The response could not be confirmed. Check the invoice before creating another payment. Retrying this form uses the same request ID.' : error instanceof Error ? error.message : 'Could not record payment.');
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }

  // 5. View
  return (
    <Stack gap="lg" maw={780}>
      <Anchor component="button" size="sm" ta="left" onClick={onBack} disabled={saving}>‹ Payments</Anchor>
      <div><Title order={1} size="h2">Add payment</Title><Text size="sm" c="dimmed">Record a full or partial settlement from HSBC GBP.</Text></div>
      {loadError ? <Alert color="red">{loadError} Return to Payments and try again.</Alert> : !invoices ? <Text role="status">Loading outstanding invoices…</Text> : invoices.length === 0 ? <Text c="dimmed">No outstanding invoices are available for payment.</Text> : (
        <Paper withBorder radius="md" p={{ base: 'md', sm: 'xl' }}>
          <form onSubmit={recordPayment}>
            <Stack gap="lg">
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                <Select label="Supplier" placeholder="Select a supplier first" searchable required value={supplierId} onChange={selectSupplier} disabled={saving} nothingFoundMessage="No matching suppliers" data={suppliers.filter((supplier) => invoices.some((row) => row.supplier_id === supplier.id)).map((supplier) => ({ value: String(supplier.id), label: suppliers.filter((row) => row.name === supplier.name).length > 1 ? `${supplier.name} · #${supplier.id}` : supplier.name }))} />
                <Select label="Invoice number" placeholder="Select an outstanding invoice" searchable required value={invoiceId} onChange={selectInvoice} disabled={!supplierId || saving} nothingFoundMessage="No outstanding invoices" data={invoices.filter((row) => row.supplier_id === Number(supplierId)).map((row) => ({ value: String(row.id), label: row.number }))} />
              </SimpleGrid>
              {invoice && <Anchor component="button" size="sm" ta="left" disabled={saving} onClick={() => onOpenInvoice(invoice.id)}>View invoice ↗</Anchor>}
              <SimpleGrid cols={{ base: 1, sm: 2 }}>
                {invoice && <TextInput label="Currency" value={invoice.currency} readOnly />}
                <TextInput label="Amount to pay" description={invoice ? `Outstanding: ${invoice.currency} ${money(invoice.balance)}` : undefined} inputWrapperOrder={['label', 'input', 'description', 'error']} placeholder="Enter payment amount" inputMode="decimal" value={amount} onChange={(event) => setAmount(event.currentTarget.value)} required disabled={!invoice || saving} />
                <DatePickerInput label="Payment date" value={date} onChange={setDate} minDate={invoice?.date} maxDate={todayString} required disabled={!invoice || saving} />
              </SimpleGrid>
              <Paper withBorder radius="md" p="md">
                <Stack gap="md">
                  <div><Text size="sm" fw={600}>Bank details</Text><Text size="sm" c="dimmed">HSBC GBP</Text></div>
                  <SimpleGrid cols={{ base: 1, sm: 2 }}>
                    <TextInput label="Exchange rate" description={invoice ? `GBP per 1 ${invoice.currency}, excluding fees` : 'Select an invoice first'} placeholder="Bank settlement rate" inputMode="decimal" value={invoice ? rate : ''} onChange={(event) => setRate(event.currentTarget.value)} required readOnly={invoice?.currency === 'GBP'} disabled={!invoice || saving} />
                    <TextInput label="Bank fees (GBP)" description="Separate from the settlement amount" inputMode="decimal" value={invoice ? fees : ''} onChange={(event) => setFees(event.currentTarget.value)} required disabled={!invoice || saving} />
                  </SimpleGrid>
                </Stack>
              </Paper>
              <TextInput label="Reference (optional)" value={reference} onChange={(event) => setReference(event.currentTarget.value)} maxLength={200} disabled={!invoice || saving} />
              {error && <Alert color="red" title="Payment not confirmed">{error}</Alert>}
              <Group justify="flex-end"><Button variant="subtle" onClick={onBack} disabled={saving}>Cancel</Button><Button type="submit" loading={saving} disabled={!invoice || !date}>Record payment</Button></Group>
            </Stack>
          </form>
        </Paper>
      )}
    </Stack>
  );
}
