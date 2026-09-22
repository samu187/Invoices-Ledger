// 1. Imports and API response type
import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Grid, Group, Paper, ScrollArea, Stack, Table, Text, TextInput, Title } from '@mantine/core';

type Supplier = { id: number; name: string; company_id: number; created_at: string };

export default function Suppliers() {
  // 2. State
  const [suppliers, setSuppliers] = useState<Supplier[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [name, setName] = useState('');
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);

  // 3. Effects
  useEffect(() => {
    let active = true;
    async function loadSuppliers() {
      try {
        const response = await fetch('/api/suppliers');
        if (!response.ok) throw new Error(`Could not load suppliers (${response.status}).`);
        const data: Supplier[] = await response.json();
        if (active) setSuppliers(data);
      } catch (error) {
        if (active) setLoadError(error instanceof Error ? error.message : 'Could not load suppliers.');
      }
    }
    loadSuppliers();
    return () => { active = false; };
  }, []);

  // 4. Helpers
  async function addSupplier(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting.current || !name.trim()) return;
    submitting.current = true;
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      const response = await fetch('/api/suppliers', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.detail === 'string' ? data.detail : Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join(' ') : 'Could not add supplier.');
      }
      const supplier: Supplier = await response.json();
      setSuppliers((rows) => [...(rows ?? []), supplier].sort((a, b) => a.name.localeCompare(b.name) || a.id - b.id));
      setName('');
      setSuccess(`${supplier.name} added.`);
    } catch (error) {
      setError(error instanceof TypeError ? 'The response could not be confirmed. Refresh the supplier list before retrying; the supplier may have been added.' : error instanceof Error ? error.message : 'Could not add supplier.');
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  }

  // 5. View
  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={1} size="h2">Suppliers</Title>
        {suppliers && <Text size="sm" c="dimmed">{suppliers.length} suppliers</Text>}
      </Group>
      <Grid gap="xl">
        <Grid.Col span={{ base: 12, sm: 7 }}>
          {loadError ? <Alert color="red" title="Suppliers unavailable">{loadError} Refresh to retry.</Alert> : !suppliers ? <Text role="status">Loading suppliers…</Text> : (
            <Stack gap="sm">
              <ScrollArea>
                <Table highlightOnHover miw={300} verticalSpacing="sm">
                  <Table.Thead><Table.Tr><Table.Th w={80}>ID</Table.Th><Table.Th>Supplier name</Table.Th></Table.Tr></Table.Thead>
                  <Table.Tbody>{suppliers.map((supplier) => <Table.Tr key={supplier.id}><Table.Td c="dimmed">#{supplier.id}</Table.Td><Table.Td>{supplier.name}</Table.Td></Table.Tr>)}</Table.Tbody>
                </Table>
              </ScrollArea>
              {suppliers.length === 0 && <Text c="dimmed">No suppliers yet. Add your first supplier alongside.</Text>}
            </Stack>
          )}
        </Grid.Col>
        <Grid.Col span={{ base: 12, sm: 5 }}>
          <Paper withBorder radius="md" p="lg">
            <form onSubmit={addSupplier}>
              <Stack gap="md">
                <Title order={2} size="h4">Add supplier</Title>
                <TextInput label="Supplier name" placeholder="Enter supplier name" value={name} onChange={(event) => { setName(event.currentTarget.value); setSuccess(''); }} maxLength={200} required disabled={saving || !suppliers} />
                {error && <Alert color="red" title="Supplier not confirmed">{error}</Alert>}
                {success && <Text size="sm" role="status">{success}</Text>}
                <Group justify="flex-end"><Button type="submit" loading={saving} disabled={!suppliers || !name.trim()}>Add supplier</Button></Group>
              </Stack>
            </form>
          </Paper>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}
