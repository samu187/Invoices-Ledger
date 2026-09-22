// 1. Imports and API response types
import { useEffect, useState } from 'react';
import { Alert, Anchor, Button, Group, Paper, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { BotIcon } from '../components/AssistantPreview';

type Outstanding = { rows: unknown[]; payables: string };
type VatMonth = { month: string; net_movement: string };

export default function Dashboard({ month, onNavigate, onOpenAssistant }: { month: string; onNavigate: (view: string) => void; onOpenAssistant: () => void }) {
  // 2. State
  const [outstanding, setOutstanding] = useState<Outstanding | null>(null);
  const [vat, setVat] = useState<VatMonth | null>(null);
  const [error, setError] = useState('');

  // 3. Effects
  useEffect(() => {
    let active = true;
    setError('');
    async function loadOverview() {
      try {
        const [outstandingResponse, vatResponse] = await Promise.all([
          fetch('/api/invoices/outstanding'),
          fetch(`/api/accounts/input-vat?month=${encodeURIComponent(month)}`),
        ]);
        if (!outstandingResponse.ok || !vatResponse.ok) throw new Error('Could not load the dashboard overview.');
        const [outstandingData, vatData]: [Outstanding, VatMonth] = await Promise.all([outstandingResponse.json(), vatResponse.json()]);
        if (active) {
          setOutstanding(outstandingData);
          setVat(vatData);
        }
      } catch (error) {
        if (active) setError(error instanceof Error ? error.message : 'Could not load the dashboard overview.');
      }
    }
    loadOverview();
    return () => { active = false; };
  }, [month]);

  // 4. Display helpers
  function money(value: string) {
    const negative = value.startsWith('-');
    const [whole, fraction = ''] = value.replace(/^-/, '').split('.');
    return `${negative ? '-' : ''}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${fraction.padEnd(2, '0')}`;
  }

  const monthLabel = new Date(`${month}-01T00:00:00`).toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

  // 5. View
  return (
    <Stack gap="xl">
      <div>
        <Title order={1} size="h2">Dashboard</Title>
        <Text c="dimmed" mt={6}>A quick view of Sample Company Demo Ltd.</Text>
      </div>

      {error ? <Alert color="red" title="Overview unavailable">{error} Refresh the page to retry.</Alert> : !outstanding || !vat ? <Text role="status">Loading overview…</Text> : (
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <Paper withBorder radius="md" p="lg">
            <Text size="sm" c="dimmed">Outstanding invoices</Text>
            <Text size="xl" fw={600} mt="xs">{outstanding.rows.length}</Text>
            <Anchor component="button" size="sm" mt="md" onClick={() => onNavigate('Invoices')}>View invoices →</Anchor>
          </Paper>
          <Paper withBorder radius="md" p="lg">
            <Text size="sm" c="dimmed">Outstanding payables</Text>
            <Text size="xl" fw={600} mt="xs" style={{ fontVariantNumeric: 'tabular-nums' }}>GBP {money(outstanding.payables)}</Text>
            <Anchor component="button" size="sm" mt="md" onClick={() => onNavigate('Invoices')}>Review balances →</Anchor>
          </Paper>
          <Paper withBorder radius="md" p="lg">
            <Text size="sm" c="dimmed">Input VAT · {monthLabel}</Text>
            <Text size="xl" fw={600} mt="xs" style={{ fontVariantNumeric: 'tabular-nums' }}>GBP {money(vat.net_movement)}</Text>
            <Anchor component="button" size="sm" mt="md" onClick={() => onNavigate('VAT')}>View VAT activity →</Anchor>
          </Paper>
        </SimpleGrid>
      )}

      <Paper withBorder radius="md" p={{ base: 'lg', sm: 'xl' }} bg="indigo.0">
        <Group justify="space-between" align="center" gap="xl" wrap="nowrap">
          <Stack gap="md" align="flex-start">
            <div>
              <Title order={2} size="h3">Put the bookkeeping assistant to work</Title>
              <Text size="sm" c="dimmed" mt={6}>Do you need AI to record invoices or payments for you? Want to ask for insights on your outstanding invoices?</Text>
            </div>
            <Button onClick={onOpenAssistant}>Ask AI Bot!</Button>
          </Stack>
          <BotIcon width={84} height={90} />
        </Group>
      </Paper>
    </Stack>
  );
}
