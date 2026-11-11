import { createContext, useContext, useState, type ReactNode } from 'react';
import type { PluginTheme } from '@getpaseo/plugin';
import { Pressable, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { Icon, Modal, ScrollView, TextInput, copyText, useToast } from '@getpaseo/plugin/client/ui';
import { markdownSegments, stateTone, toneIcon, type Tone } from './presentation';

export const Compact = createContext(true);
export const Theme = createContext<PluginTheme | null>(null);
export function useColors() { const theme = useContext(Theme); if (!theme) throw new Error('Autowork theme missing'); return theme.colors; }
export function toneColor(colors: PluginTheme['colors'], tone: Tone | 'accent'): string {
  return tone === 'success' ? colors.statusSuccess : tone === 'warning' ? colors.statusWarning : tone === 'danger' ? colors.statusDanger : tone === 'accent' ? colors.accent : colors.foregroundMuted;
}

type LabelProps = { children: ReactNode; muted?: boolean; mono?: boolean; size?: 'caption' | 'body' | 'title'; bold?: boolean; truncate?: boolean };
export function Label({ children, muted = false, mono = false, size = 'body', bold = false, truncate = false }: LabelProps) {
  const colors = useColors();
  const fontSize = size === 'caption' ? 13 : size === 'title' ? 20 : 15;
  return <Text selectable numberOfLines={truncate ? 1 : undefined} style={{ color: muted ? colors.foregroundMuted : colors.foreground, fontSize,
    lineHeight: fontSize + 6, fontWeight: bold ? '600' : '400', ...(mono ? { fontFamily: 'monospace' } : {}) }}>{children}</Text>;
}
export function Caption({ children, truncate = false }: { children: ReactNode; truncate?: boolean }) { return <Label muted size="caption" truncate={truncate}>{children}</Label>; }
export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 | 3 }) {
  const colors = useColors();
  const compact = useContext(Compact);
  const size = level === 1 ? (compact ? 28 : 34) : level === 2 ? 21 : 16;
  return <Text accessibilityRole="header" style={{ color: colors.foreground, fontSize: size, lineHeight: size + 6, fontWeight: '600', letterSpacing: level === 1 ? -0.6 : -0.2, flexShrink: 1 }}>{children}</Text>;
}
export function Divider() { const colors = useColors(); return <View style={{ height: 1, backgroundColor: colors.border, marginVertical: 4 }} />; }
export function Card({ children, compact = false, tone }: { children: ReactNode; compact?: boolean; tone?: Tone }) {
  const colors = useColors();
  return <View style={{ padding: compact ? 16 : 22, gap: compact ? 10 : 16, borderLeftWidth: tone && tone !== 'neutral' ? 3 : 0, borderColor: tone && tone !== 'neutral' ? toneColor(colors, tone) : colors.border, borderRadius: 14, backgroundColor: colors.surface1 }}>{children}</View>;
}
export function Row({ children, between = false, style }: { children: ReactNode; between?: boolean; style?: StyleProp<ViewStyle> }) {
  return <View style={[{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, ...(between ? { justifyContent: 'space-between' } : {}) }, style]}>{children}</View>;
}
export function Stack({ children, gap = 6 }: { children: ReactNode; gap?: number }) { return <View style={{ gap }}>{children}</View>; }
export function ScrollRow({ children }: { children: ReactNode }) {
  return <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingVertical: 1, paddingRight: 24 }}>{children}</ScrollView>;
}
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
/** One shape for every action; weight comes from the variant, size from compact. The host's 48px target is kept. */
export function Button({ label, onPress, disabled = false, selected = false, variant = 'secondary', compact = false, accessibilityLabel }: {
  label: string; onPress: () => void; disabled?: boolean; selected?: boolean; variant?: ButtonVariant; compact?: boolean; accessibilityLabel?: string;
}) {
  const colors = useColors();
  // A disabled control never wears the accent: it looks inert, not like a green action that ignores taps.
  const danger = variant === 'danger';
  const primary = !disabled && !danger && (variant === 'primary' || selected);
  const background = danger && selected ? colors.statusDanger : primary ? colors.accent : variant === 'ghost' ? colors.surface1 : colors.surface2;
  const foreground = disabled ? colors.foregroundMuted : danger ? (selected ? colors.accentForeground : colors.statusDanger) : primary ? colors.accentForeground : colors.foreground;
  return <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? label} accessibilityState={{ disabled, selected }} disabled={disabled} onPress={onPress}
    style={{ alignSelf: 'flex-start', minHeight: 48, minWidth: 48, paddingHorizontal: compact ? 10 : 16, paddingVertical: compact ? 6 : 10,
      justifyContent: 'center', maxWidth: '100%', borderRadius: 9, borderWidth: 1, borderStyle: disabled ? 'dashed' : 'solid',
      borderColor: disabled ? colors.border : danger ? colors.statusDanger : selected ? colors.accent : variant === 'ghost' ? colors.surface1 : colors.border, backgroundColor: background, opacity: disabled ? 0.6 : 1 }}>
    <Text style={{ color: foreground, fontSize: compact ? 14 : 15, fontWeight: '600', textAlign: 'center' }}>{label}</Text>
  </Pressable>;
}
export function IconButton({ label, icon, onPress, disabled = false }: { label: string; icon: string; onPress: () => void; disabled?: boolean }) {
  const colors = useColors();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={{ alignSelf: 'flex-start', minHeight: 48, minWidth: 48, alignItems: 'center', justifyContent: 'center', borderRadius: 9, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface2, opacity: disabled ? 0.5 : 1 }}>
    <Icon name={icon} size={18} color={disabled ? colors.foregroundMuted : colors.foreground} />
  </Pressable>;
}
export function Stat({ value, label, tone = 'neutral' }: { value: string | number; label: string; tone?: Tone }) {
  const colors = useColors();
  return <View accessible accessibilityLabel={`${value} ${label}`} style={{ minWidth: 90, flexDirection: 'row', alignItems: 'baseline', gap: 7, paddingVertical: 8, paddingRight: 20 }}>
    <Text style={{ color: tone === 'neutral' ? colors.foreground : toneColor(colors, tone), fontSize: 22, fontWeight: '600', fontVariant: ['tabular-nums'] }}>{value}</Text>
    <Text style={{ color: colors.foregroundMuted, fontSize: 13 }}>{label}</Text>
  </View>;
}
export function Badge({ label, tone = 'neutral' }: { label: string; tone?: Tone | 'accent' }) {
  const colors = useColors();
  const color = toneColor(colors, tone);
  return <View style={{ alignSelf: 'flex-start', maxWidth: '100%', paddingHorizontal: 7, paddingVertical: 4, borderRadius: 5, backgroundColor: colors.surface2, borderColor: color }}>
    <Text style={{ color, fontSize: 12, fontWeight: '500', flexShrink: 1 }}>{label}</Text>
  </View>;
}
/** A state with its colour, an icon that says the same thing, and the words themselves. */
export function StatusPill({ state, tone }: { state: string; tone?: Tone }) {
  const colors = useColors();
  const resolved = tone ?? stateTone(state);
  const color = toneColor(colors, resolved);
  return <View accessibilityLabel={`status ${state}`} style={{ flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', maxWidth: '100%', paddingHorizontal: 7, paddingVertical: 4, borderRadius: 5, backgroundColor: colors.surface2, borderColor: color }}>
    <Icon name={toneIcon(resolved)} size={13} color={color} />
    <Text style={{ color, fontSize: 12, fontWeight: '500', flexShrink: 1 }}>{state}</Text>
  </View>;
}
export function Notice({ children, tone = 'neutral' }: { children: ReactNode; tone?: Tone }) {
  const colors = useColors();
  const color = tone === 'neutral' ? colors.border : toneColor(colors, tone);
  return <View accessibilityRole="summary" style={{ padding: 10, borderWidth: 1, borderColor: color, backgroundColor: colors.surface2, borderRadius: 8 }}>
    <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
      <Icon name={toneIcon(tone)} size={16} color={tone === 'neutral' ? colors.foregroundMuted : color} />
      <View style={{ flex: 1, gap: 4 }}>{children}</View>
    </View>
  </View>;
}
/** The one line a screen leads with: what state matters most and the single next action. */
export function Banner({ tone, title, body, action, secondary }: { tone: Tone; title: string; body?: string; action?: { label: string; onPress: () => void; disabled?: boolean }; secondary?: { label: string; onPress: () => void } }) {
  const colors = useColors();
  const color = toneColor(colors, tone);
  return <View accessibilityRole="summary" style={{ padding: 24, gap: 20, borderRadius: 16, borderLeftWidth: 3, borderColor: color, backgroundColor: colors.surface1 }}>
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
      <Icon name={toneIcon(tone)} size={18} color={color} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={{ color: colors.foreground, fontSize: 24, lineHeight: 30, fontWeight: '600', letterSpacing: -0.4 }}>{title}</Text>
        {body ? <Text style={{ color: colors.foregroundMuted, fontSize: 15, lineHeight: 23, maxWidth: 650 }}>{body}</Text> : null}
      </View>
    </View>
    {action || secondary ? <Row>
      {action ? <Button label={action.label} variant="primary" compact disabled={action.disabled} onPress={action.onPress} /> : null}
      {secondary ? <Button label={secondary.label} compact onPress={secondary.onPress} /> : null}
    </Row> : null}
  </View>;
}
export function KeyValue({ name, value, mono = false }: { name: string; value: ReactNode; mono?: boolean }) {
  return <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
    <View style={{ width: 112 }}><Caption>{name}</Caption></View>
    <View style={{ flex: 1 }}>{typeof value === 'string' ? <Label mono={mono}>{value}</Label> : value}</View>
  </View>;
}
/** Labelled facts; an empty list renders nothing rather than a row of unknowns. */
export function Facts({ rows }: { rows: Array<[string, string]> }) {
  if (!rows.length) return null;
  return <View style={{ gap: 3 }}>{rows.map(([name, value]) => <KeyValue key={name} name={name} value={value} />)}</View>;
}
export function Input({ label, value, onChange, multiline = false, placeholder, hint }: { label: string; value: string; onChange: (text: string) => void; multiline?: boolean; placeholder?: string; hint?: string }) {
  const colors = useColors();
  return <View style={{ gap: 4 }}>
    <Caption>{label}</Caption>
    <TextInput accessibilityLabel={label} value={value} onChangeText={onChange} multiline={multiline} maxLength={16000} placeholder={placeholder} placeholderTextColor={colors.foregroundMuted}
      style={{ minHeight: multiline ? 88 : 48, color: colors.foreground, backgroundColor: colors.surface0, borderColor: colors.border, borderWidth: 1, borderRadius: 8, padding: 10, textAlignVertical: multiline ? 'top' : 'center' }} />
    {hint ? <Caption>{hint}</Caption> : null}
  </View>;
}
/** A segmented choice: one selected option, the rest quiet. */
export function Choice<T extends string>({ label, value, options, onChange, disabled = false, danger = [] }: { label: string; value: T; options: readonly (T | readonly [T, string])[]; onChange: (value: T) => void; disabled?: boolean; danger?: readonly T[] }) {
  const items = options.map(option => (typeof option === 'string' ? [option, option] : [option[0], option[1]]) as [T, string]);
  return <View style={{ gap: 4 }}>
    <Caption>{label}</Caption>
    <Row>{items.map(([key, title]) => <Button key={key} label={title} compact variant={danger.includes(key) ? 'danger' : 'secondary'} selected={value === key} disabled={disabled} onPress={() => onChange(key)} />)}</Row>
  </View>;
}
/** A quiet disclosure row: expanded content never turns the header into a primary action. */
export function Expand({ title, children, open = false, hint, onToggle }: { title: string; children: ReactNode; open?: boolean; hint?: string; onToggle?: (expanded: boolean) => void }) {
  const colors = useColors();
  const [expanded, setExpanded] = useState(open);
  return <View style={{ gap: 4 }}>
    <Pressable accessibilityRole="button" accessibilityLabel={title} accessibilityState={{ expanded }} onPress={() => { const next = !expanded; setExpanded(next); onToggle?.(next); }}
      style={{ alignSelf: 'flex-start', minHeight: 48, minWidth: 48, flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 10, borderRadius: 9, backgroundColor: colors.surface2 }}>
      <Icon name={expanded ? 'ChevronDown' : 'ChevronRight'} size={16} color={colors.foregroundMuted} />
      <Text style={{ color: colors.foreground, fontSize: 13, fontWeight: '600' }}>{title}</Text>
    </Pressable>
    {hint ? <Caption>{hint}</Caption> : null}
    {expanded ? <View style={{ gap: 6 }}>{children}</View> : null}</View>;
}
/** Owner text rendered as text: bold, code and links show their words, not their Markdown. */
export function Markdown({ text }: { text: string }) {
  const colors = useColors();
  const paragraphs = text.split(/\n{2,}/).map(item => item.trim()).filter(Boolean);
  return <View style={{ gap: 6 }}>{paragraphs.map((paragraph, index) => <Text key={index} selectable style={{ color: colors.foreground, fontSize: 15, lineHeight: 23 }}>
    {markdownSegments(paragraph.replace(/^#+\s*/gm, '').replace(/^\s*[-*]\s+/gm, '• ')).map((segment, position) => <Text key={position} style={{
      fontWeight: segment.bold ? '700' : '400', ...(segment.code ? { fontFamily: 'monospace' } : {}),
      ...(segment.link ? { color: colors.accent, textDecorationLine: 'underline' } : {}) }}>{segment.text}</Text>)}
  </Text>)}</View>;
}
/** A short hash the eye can hold, with the full value one tap away. */
export function HashChip({ value, name, suffix = '' }: { value: string; name: string; suffix?: string }) {
  const toast = useToast();
  const short = value ? value.slice(0, 8) : 'unknown';
  return <Row>
    <Label mono>{short}{suffix ? ` · ${suffix.replace(/^\+/, '')}` : ''}</Label>
    {value ? <IconButton label={`Copy ${name} ${short}`} icon="Copy" onPress={() => { void copyText(value).then(() => toast.show(`Copied ${name} ${value}`, { variant: 'info', durationMs: 2000 })).catch(() => toast.error('Copy unavailable on this client')); }} /> : null}
  </Row>;
}
/** The host's sheet (bottom sheet on phones, dialog on desktop) for a step that must not be missed. */
export function Sheet({ title, open, onClose, children }: { title: string; open: boolean; onClose: () => void; children: ReactNode }) {
  // A native modal body renders in the host's portal host. The host rebuilds only its own
  // runtime contexts there, so this plugin's theme context is absent and every label in the
  // body would throw. Re-provide the ambient theme inside the body.
  const theme = useContext(Theme);
  return <Modal title={title} open={open} onOpenChange={next => { if (!next) onClose(); }}>
    <Modal.Content><Theme.Provider value={theme}><View style={{ gap: 10 }}>{children}</View></Theme.Provider></Modal.Content>
  </Modal>;
}

/** Navigation has a quiet selected underline; filled accents are reserved for actions. */
export function NavItem({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  const colors = useColors();
  return <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ selected }} onPress={onPress}
    style={{ minWidth: 48, minHeight: 48, paddingHorizontal: 14, justifyContent: 'center', borderBottomWidth: 2,
      borderBottomColor: selected ? colors.accent : colors.border, backgroundColor: selected ? colors.surface2 : colors.surface0 }}>
    <Text style={{ color: selected ? colors.foreground : colors.foregroundMuted, fontSize: 15, fontWeight: selected ? '600' : '400' }}>{label}</Text>
  </Pressable>;
}
/** Evidence leads on desktop; actions sit alongside it, stacking in reading order on mobile. */
export function Workspace({ primary, secondary }: { primary: ReactNode; secondary: ReactNode }) {
  const compact = useContext(Compact);
  return <View accessibilityLabel="Runner workspace" style={{ flexDirection: compact ? 'column' : 'row', alignItems: 'stretch', gap: 24 }}>
    <View style={{ flex: compact ? undefined : 3, minWidth: 0, gap: 20 }}>{primary}</View>
    <View style={{ flex: compact ? undefined : 2, minWidth: 0, gap: 20 }}>{secondary}</View>
  </View>;
}
