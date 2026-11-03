import { createContext, useContext, useState, type ReactNode } from 'react';
import type { PluginTheme } from '@getpaseo/plugin';
import { Pressable, Text, View } from 'react-native';
import { ScrollView, TextInput } from '@getpaseo/plugin/client/ui';

export const Theme = createContext<PluginTheme | null>(null);
export function useColors() { const theme = useContext(Theme); if (!theme) throw new Error('Autowork theme missing'); return theme.colors; }

type LabelProps = { children: ReactNode; muted?: boolean; mono?: boolean; size?: 'caption' | 'body' | 'title'; bold?: boolean; truncate?: boolean };
export function Label({ children, muted = false, mono = false, size = 'body', bold = false, truncate = false }: LabelProps) {
  const colors = useColors();
  const fontSize = size === 'caption' ? 12 : size === 'title' ? 17 : 14;
  return <Text selectable numberOfLines={truncate ? 1 : undefined} style={{ color: muted ? colors.foregroundMuted : colors.foreground, fontSize,
    lineHeight: fontSize + 6, fontWeight: bold ? '600' : '400', ...(mono ? { fontFamily: 'monospace' } : {}) }}>{children}</Text>;
}
export function Caption({ children, truncate = false }: { children: ReactNode; truncate?: boolean }) { return <Label muted size="caption" truncate={truncate}>{children}</Label>; }
export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 }) {
  const colors = useColors();
  return <Text accessibilityRole="header" style={{ color: colors.foreground, fontSize: level === 1 ? 22 : 17, lineHeight: level === 1 ? 28 : 23, fontWeight: '700' }}>{children}</Text>;
}
export function Divider() { const colors = useColors(); return <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 4 }} />; }
export function Card({ children, compact = false }: { children: ReactNode; compact?: boolean }) {
  const colors = useColors();
  return <View style={{ padding: compact ? 10 : 14, gap: compact ? 6 : 9, borderWidth: 1, borderColor: colors.border, borderRadius: 12, backgroundColor: colors.surface1 }}>{children}</View>;
}
export function Row({ children }: { children: ReactNode }) { return <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>{children}</View>; }
export function Stack({ children, gap = 6 }: { children: ReactNode; gap?: number }) { return <View style={{ gap }}>{children}</View>; }
export function ScrollRow({ children }: { children: ReactNode }) {
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 1 }}>{children}</ScrollView>;
}
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export function Button({ label, onPress, disabled = false, selected = false, variant = 'secondary', compact = false }: {
  label: string; onPress: () => void; disabled?: boolean; selected?: boolean; variant?: ButtonVariant; compact?: boolean;
}) {
  const colors = useColors();
  const primary = variant === 'primary' || selected;
  const background = primary ? colors.accent : colors.surface2;
  const foreground = primary ? colors.accentForeground : variant === 'danger' ? colors.statusDanger : colors.foreground;
  // Keep the host's 48px accessible target; compact only reduces visual padding.
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled, selected }} disabled={disabled} onPress={onPress}
    style={{ alignSelf: 'flex-start', minHeight: 48, minWidth: 48, paddingHorizontal: compact ? 10 : 14, paddingVertical: compact ? 6 : 10,
      justifyContent: 'center', borderRadius: 9, borderWidth: 1,
      borderColor: selected ? colors.accent : colors.border, backgroundColor: background, opacity: disabled ? 0.4 : 1 }}>
    <Text style={{ color: foreground, fontSize: compact ? 13 : 14, fontWeight: '600', textAlign: 'center' }}>{label}</Text>
  </Pressable>;
}
export function IconButton({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
  return <Button label={label} onPress={onPress} disabled={disabled} compact variant="ghost" />;
}
export function Stat({ value, label, tone = 'neutral' }: { value: string | number; label: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' }) {
  const colors = useColors();
  const color = tone === 'success' ? colors.statusSuccess : tone === 'warning' ? colors.statusWarning : tone === 'danger' ? colors.statusDanger : colors.foreground;
  return <View style={{ minWidth: 74, flexGrow: 1, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 10, backgroundColor: colors.surface2 }}>
    <Text style={{ color, fontSize: 20, fontWeight: '700' }}>{value}</Text>
    <Text style={{ color: colors.foregroundMuted, fontSize: 11 }}>{label}</Text>
  </View>;
}
export function Badge({ label, tone = 'neutral' }: { label: string; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'accent' }) {
  const colors = useColors();
  const color = tone === 'success' ? colors.statusSuccess : tone === 'warning' ? colors.statusWarning : tone === 'danger' ? colors.statusDanger : tone === 'accent' ? colors.accent : colors.foregroundMuted;
  return <View style={{ alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, borderWidth: 1, borderColor: color }}>
    <Text style={{ color, fontSize: 11, fontWeight: '700', textTransform: 'uppercase' }}>{label}</Text>
  </View>;
}
export function Notice({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'warning' | 'danger' | 'success' }) {
  const colors = useColors();
  const color = tone === 'danger' ? colors.statusDanger : tone === 'warning' ? colors.statusWarning : tone === 'success' ? colors.statusSuccess : colors.foregroundMuted;
  return <View style={{ padding: 10, gap: 4, borderLeftWidth: 3, borderLeftColor: color, backgroundColor: colors.surface2, borderRadius: 6 }}>{children}</View>;
}
export function KeyValue({ name, value, mono = false }: { name: string; value: ReactNode; mono?: boolean }) {
  return <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
    <View style={{ width: 112 }}><Caption>{name}</Caption></View>
    <View style={{ flex: 1 }}>{typeof value === 'string' ? <Label mono={mono}>{value}</Label> : value}</View>
  </View>;
}
export function Input({ label, value, onChange, multiline = false }: { label: string; value: string; onChange: (text: string) => void; multiline?: boolean }) {
  const colors = useColors();
  return <View style={{ gap: 4 }}>
    <Caption>{label}</Caption>
    <TextInput accessibilityLabel={label} value={value} onChangeText={onChange} multiline={multiline} maxLength={16000} placeholderTextColor={colors.foregroundMuted} style={{ minHeight: multiline ? 88 : 42, color: colors.foreground, backgroundColor: colors.surface0, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 10, textAlignVertical: multiline ? 'top' : 'center' }} />
  </View>;
}
export function Expand({ title, children }: { title: string; children: ReactNode }) {
  const [expanded, setExpanded] = useState(false);
  return <View style={{ gap: 8 }}>
    <Button label={title} onPress={() => setExpanded(!expanded)} selected={expanded} compact />{expanded ? <View style={{ gap: 6 }}>{children}</View> : null}</View>;
}
