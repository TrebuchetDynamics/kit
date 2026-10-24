import { createContext, useContext, useState, type ReactNode } from 'react';
import type { PluginTheme } from '@getpaseo/plugin';
import { Pressable, Text, View } from 'react-native';
import { TextInput } from '@getpaseo/plugin/client/ui';

export const Theme = createContext<PluginTheme | null>(null);
export function useColors() { const theme = useContext(Theme); if (!theme) throw new Error('Autowork theme missing'); return theme.colors; }
export function Label({ children, muted = false, mono = false }: { children: ReactNode; muted?: boolean; mono?: boolean }) {
  const colors = useColors();
  return <Text selectable style={{ color: muted ? colors.foregroundMuted : colors.foreground, fontSize: 15, lineHeight: 22, ...(mono ? { fontFamily: 'monospace' } : {}) }}>{children}</Text>;
}
export function Heading({ children }: { children: ReactNode }) { const colors = useColors(); return <Text accessibilityRole="header" style={{ color: colors.foreground, fontSize: 20, fontWeight: '600' }}>{children}</Text>; }
export function Card({ children }: { children: ReactNode }) { const colors = useColors(); return <View style={{ padding: 16, gap: 10, borderWidth: 1, borderColor: colors.border, borderRadius: 12, backgroundColor: colors.surface1 }}>{children}</View>; }
export function Row({ children }: { children: ReactNode }) { return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>{children}</View>; }
export function Button({ label, onPress, disabled = false, selected = false }: { label: string; onPress: () => void; disabled?: boolean; selected?: boolean }) {
  const colors = useColors();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, selected }} disabled={disabled} onPress={onPress} style={{ minHeight: 48, minWidth: 48, paddingHorizontal: 14, paddingVertical: 13, justifyContent: 'center', borderRadius: 8, borderWidth: 1, borderColor: colors.border, backgroundColor: selected ? colors.accent : colors.surface2, opacity: disabled ? 0.5 : 1 }}>
    <Text style={{ color: selected ? colors.accentForeground : colors.foreground, fontSize: 15 }}>{label}</Text>
  </Pressable>;
}
export function Input({ label, value, onChange, multiline = false }: { label: string; value: string; onChange: (text: string) => void; multiline?: boolean }) {
  const colors = useColors();
  return <View style={{ gap: 4 }}>
    <Label muted>{label}</Label>
    <TextInput accessibilityLabel={label} value={value} onChangeText={onChange} multiline={multiline} maxLength={16000} placeholderTextColor={colors.foregroundMuted} style={{ minHeight: multiline ? 96 : 48, color: colors.foreground, backgroundColor: colors.surface0, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 12, textAlignVertical: multiline ? 'top' : 'center' }} />
  </View>;
}
export function Expand({ title, children }: { title: string; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  return <View style={{ gap: 8 }}>
    <Button label={title} onPress={() => setExpanded(!expanded)} selected={expanded} />{expanded ? children : null}</View>;
}
