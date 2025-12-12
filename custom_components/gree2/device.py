import logging
import asyncio

from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.components.climate import ClimateEntity
from homeassistant.helpers.event import async_track_state_change_event

from homeassistant.components.climate.const import (
    HVACMode, ClimateEntityFeature,
    FAN_AUTO, FAN_LOW, FAN_MIDDLE, FAN_HIGH,
    PRESET_NONE, PRESET_SLEEP)

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, ATTR_TEMPERATURE, CONF_SCAN_INTERVAL,
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_MAC, CONF_TIMEOUT, CONF_CUSTOMIZE,
    STATE_ON, STATE_OFF, STATE_UNKNOWN,
    UnitOfTemperature, PRECISION_WHOLE, PRECISION_TENTHS)

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 7000

# from the remote control and gree app
MIN_TEMP = 16
MAX_TEMP = 30

# fixed values in gree mode lists
HVAC_MODES = [HVACMode.AUTO, HVACMode.COOL, HVACMode.DRY,
              HVACMode.FAN_ONLY, HVACMode.HEAT, HVACMode.OFF]
FAN_MODES = [FAN_AUTO, FAN_LOW, 'medium-low',
             FAN_MIDDLE, 'medium-high', FAN_HIGH]
PRESET_MODES = [PRESET_NONE, PRESET_SLEEP]

SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.PRESET_MODE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON


class Gree2Climate(ClimateEntity):

    def __init__(self, hass, name, mac, bridge, temp_sensor, temp_step):
        _LOGGER.info('Initialize the GREE climate device')
        self.hass = hass
        self.mac = mac

        self._unique_id = 'com.gree2.' + mac

        self._available = False

        self._name = name

        self._bridge = bridge

        self._unit_of_measurement = hass.config.units.temperature_unit

        self._target_temperature = 26
        self._current_temperature = 26
        self._target_temperature_step = temp_step
        self._hvac_mode = HVACMode.OFF
        self._fan_mode = FAN_AUTO
        self._preset_mode = PRESET_NONE

        self._hvac_modes = HVAC_MODES
        self._fan_modes = FAN_MODES
        self._preset_modes = PRESET_MODES

        self._temp_sensor = temp_sensor
        if temp_sensor:
            async_track_state_change_event(
                hass, temp_sensor, self._async_temp_sensor_changed)
            temp_state = hass.states.get(temp_sensor)
            if temp_state:
                self._async_update_current_temp(temp_state)

        self._acOptions = {
            'Pow': 0,
            'Mod': 0,  # 使用数字索引而不是字符串
            'WdSpd': 0,
            'SetTem': 26,
            'Air': 0,
            'Blo': 0,
            'Health': 0,
            'SwhSlp': 0,
            'SwingLfRig': 0,
            'Quiet': 0,
            'SvSt': 0,
            'Add0.1': 0
    }

    @property
    def should_poll(self):
        # Return the polling state.
        return False

    @property
    def unique_id(self) -> str:
        # Return a unique ID.
        return self._unique_id

    @property
    def available(self):
        # Return available of the climate device.
        return self._available

    @property
    def hidden(self):
        # Return hidden of the climate device.
        return not self._available

    @property
    def name(self):
        # Return the name of the climate device.
        return self._name

    @property
    def temperature_unit(self):
        # Return the unit of measurement.
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        # Return the current temperature.
        return self._current_temperature

    @property
    def target_temperature(self):
        # Return the temperature we try to reach.
        return self._target_temperature

    @property
    def target_temperature_step(self):
        # Return the supported step of target temperature.
        return self._target_temperature_step

    @property
    def min_temp(self):
        # Return the minimum temperature.
        return MIN_TEMP

    @property
    def max_temp(self):
        # Return the maximum temperature.
        return MAX_TEMP

    @property
    def hvac_mode(self):
        # Return current operation mode ie. heat, cool, idle.
        return self._hvac_mode

    @property
    def hvac_modes(self):
        # Return the list of available operation modes.
        return self._hvac_modes

    @property
    def fan_mode(self):
        # Return the fan mode.
        return self._fan_mode

    @property
    def fan_modes(self):
        # Return the list of available fan modes.
        return self._fan_modes

    @property
    def preset_mode(self):
        # Return the preset mode.
        if self._acOptions['SwhSlp'] != 0:
            return PRESET_SLEEP
        return PRESET_NONE

    @property
    def preset_modes(self):
        # Return the list of available preset modes.
        return self._preset_modes

    @property
    def supported_features(self):
        # Return the list of supported features.
        return SUPPORT_FLAGS

    def turn_on(self):
        _LOGGER.info('turn_on(): ')
        # Turn on.
        self.syncState({'Pow': 1})

    def turn_off(self):
        _LOGGER.info('turn_off(): ')
        # Turn on.
        self.syncState({'Pow': 0})

    def set_temperature(self, **kwargs):
        _LOGGER.info('set_temperature(): ' + str(kwargs.get(ATTR_TEMPERATURE)))
        # Set new target temperatures.
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            # do nothing if temperature is none
            if not (self._acOptions['Pow'] == 0):
                # do nothing if HVAC is switched off
                _LOGGER.info('syncState with SetTem=' +
                             str(kwargs.get(ATTR_TEMPERATURE)))
                tem, decimal = str(kwargs.get(ATTR_TEMPERATURE)).split('.')
                self.syncState({'SetTem': int(tem), 'Add0.1': int(decimal)})

    def set_fan_mode(self, fan):
        _LOGGER.info('set_fan_mode(): ' + str(fan))
        # Set the fan mode.
        if not (self._acOptions['Pow'] == 0):
            _LOGGER.info('Setting normal fan mode to ' +
                         str(self._fan_modes.index(fan)))
            self.syncState({'WdSpd': str(self._fan_modes.index(fan))})

    def set_hvac_mode(self, hvac_mode):
        _LOGGER.info('set_hvac_mode(): ' + str(hvac_mode))
        # Set new operation mode.
        if (hvac_mode == HVACMode.OFF):
            self.syncState({'Pow': 0})
        else:
            self.syncState(
                {'Mod': self._hvac_modes.index(hvac_mode), 'Pow': 1})

    def set_preset_mode(self, preset_mode):
        _LOGGER.info('set_preset_mode(): ' + str(preset_mode))
        # Set the fan mode.
        if self._acOptions['Pow'] == 0:
            return

        if preset_mode == PRESET_SLEEP:
            _LOGGER.info('Setting SwhSlp mode to 1')
            self.syncState({'SwhSlp': 1, 'Quiet': 1})
            return

        self.syncState({'SwhSlp': 0, 'Quiet': 0})

    async def async_added_to_hass(self):
        _LOGGER.info('Gree climate device added to hass()')
        self.syncStatus()

    def syncStatus(self, now=None):
        cmds = ['Pow', 'Mod', 'SetTem', 'WdSpd', 'Air', 'Blo',
                'Health', 'SwhSlp', 'SwingLfRig', 'Quiet', 'SvSt', 'Add0.1']
        message = {
            'cols': cmds,
            'mac': self.mac,
            't': 'status'
        }
        self._bridge.sync_status(message)

    def dealStatusPack(self, statusPack):
        if statusPack is not None:
            self._available = True
            try:
            # 验证数据完整性
                if not isinstance(statusPack, dict) or 'cols' not in statusPack or 'dat' not in statusPack:
                    _LOGGER.warning(f"Invalid status pack structure for {self._name}: {statusPack}")
                    return
                
                cols = statusPack['cols']
                dat = statusPack['dat']
            
            # 确保cols和dat长度匹配
                min_length = min(len(cols), len(dat))
                if len(cols) != len(dat):
                    _LOGGER.warning(f"Data length mismatch for {self._name}. cols: {len(cols)}, dat: {len(dat)}")
            
            # 安全处理每个字段
                for i in range(min_length):
                    col_name = cols[i]
                    data_value = dat[i]
                
                # 清洗和验证数据
                    cleaned_value = self._cleanDataValue(col_name, data_value)
                    self._acOptions[col_name] = cleaned_value
                
                _LOGGER.info('Climate {} status: {}'.format(self._name, self._acOptions))
                self.UpdateHAStateToCurrentACState()
                self.schedule_update_ha_state()
            
            except Exception as e:
                _LOGGER.error(f"Error processing status pack for {self._name}: {e}")
                _LOGGER.debug(f"Problematic data: {statusPack}")
                # 即使处理失败，也不要将设备标记为不可用，保持最后已知状态
                # self._available = False
                self.schedule_update_ha_state()

    def _cleanDataValue(self, col_name, value):
        """清洗和验证数据值"""
    # 处理空值
        if value == "" or value is None:
        # 根据字段类型返回适当的默认值
            numeric_fields = ['Pow', 'Mod', 'WdSpd', 'SetTem', 'Air', 'Blo', 
                         'Health', 'SwhSlp', 'SwingLfRig', 'Quiet', 'SvSt', 'Add0.1']
            return 0 if col_name in numeric_fields else ""
    
    # 确保数值字段是数字类型
        try:
            if col_name in ['Pow', 'Mod', 'WdSpd', 'SetTem', 'Air', 'Blo', 
                       'Health', 'SwhSlp', 'SwingLfRig', 'Quiet', 'SvSt', 'Add0.1']:
                return int(value) if str(value).isdigit() else 0
        except (ValueError, TypeError):
            _LOGGER.warning(f"Failed to convert {col_name} value '{value}' to int for {self._name}")
            return 0
    
        return value

    def dealResPack(self, resPack):
        if resPack is not None:
            try:
                if not isinstance(resPack, dict) or 'opt' not in resPack or 'val' not in resPack:
                    _LOGGER.warning(f"Invalid response pack structure for {self._name}: {resPack}")
                    return
                
                opt = resPack['opt']
                val = resPack['val']
            
                min_length = min(len(opt), len(val))
                for i in range(min_length):
                    opt_name = opt[i]
                    opt_value = val[i]
                    cleaned_value = self._cleanDataValue(opt_name, opt_value)
                    self._acOptions[opt_name] = cleaned_value
                
                self.UpdateHAStateToCurrentACState()
                self.schedule_update_ha_state()
            
            except Exception as e:
                _LOGGER.error(f"Error processing response pack for {self._name}: {e}")
                self.schedule_update_ha_state()

    def syncState(self, options):
        commands = []
        values = []
        for cmd in options.keys():
            commands.append(cmd)
            values.append(int(options[cmd]))
        message = {
            'opt': commands,
            'p': values,
            't': 'cmd',
            'sub': self.mac
        }
        self._bridge.sync_status(message)

    def UpdateHATargetTemperature(self):
        """Sync set temperature to HA with error handling"""
        try:
            tem = 26  # 默认温度
            if 'SetTem' in self._acOptions:
                set_tem_value = self._acOptions['SetTem']
                if set_tem_value != "" and set_tem_value is not None:
                    tem = int(set_tem_value)
        
        # 处理小数温度
            if 'Add0.1' in self._acOptions:
                decimal_value = self._acOptions['Add0.1']
                if decimal_value != "" and decimal_value is not None:
                    try:
                        decimal = int(decimal_value)
                        if decimal:
                            tem = tem + decimal * 0.1
                    except (ValueError, TypeError):
                        pass  # 忽略小数部分错误
        
            self._target_temperature = tem
            _LOGGER.info('{} HA target temp set according to HVAC state to: {}'.format(
                self._name, str(tem)))
            
        except Exception as e:
            _LOGGER.error(f"Error updating target temperature for {self._name}: {e}")
        # 设置安全默认值
            self._target_temperature = 26

    def UpdateHAHvacMode(self):
        """Sync current HVAC operation mode to HA with error handling"""
        try:
            power = 0
            if 'Pow' in self._acOptions:
                power_value = self._acOptions['Pow']
                if power_value != "" and power_value is not None:
                    power = int(power_value)
        
            if power == 0:
                self._hvac_mode = HVACMode.OFF
            else:
                mode_index = 0  # 默认制冷模式
                if 'Mod' in self._acOptions:
                    mod_value = self._acOptions['Mod']
                    if mod_value != "" and mod_value is not None:
                        mode_index = int(mod_value)
            
                if mode_index < len(self._hvac_modes):
                    self._hvac_mode = self._hvac_modes[mode_index]
                else:
                    _LOGGER.warning(f"Invalid mode index {mode_index} for {self._name}, using default")
                    self._hvac_mode = HVACMode.COOL
                
            _LOGGER.info('{} HA operation mode set according to HVAC state to: {}'.format(
                self._name, str(self._hvac_mode)))
            
        except Exception as e:
            _LOGGER.error(f"Error updating HVAC mode for {self._name}: {e}")
            self._hvac_mode = HVACMode.OFF

    def UpdateHAFanMode(self):
        """Sync current HVAC Fan mode state to HA with error handling"""
        try:
            index = 0  # 默认自动模式
            if 'WdSpd' in self._acOptions:
                wdspd_value = self._acOptions['WdSpd']
                if wdspd_value != "" and wdspd_value is not None:
                    index = int(wdspd_value)
        
            if index < len(self._fan_modes):
                self._fan_mode = self._fan_modes[index]
                _LOGGER.info('{} HA fan mode set according to HVAC state to: {}'.format(
                    self._name, str(self._fan_mode)))
            else:
                _LOGGER.warning('{} HA fan mode index out of range: {}'.format(
                    self._name, str(index)))
                self._fan_mode = FAN_AUTO  # 使用默认值
            
        except Exception as e:
            _LOGGER.error(f"Error updating fan mode for {self._name}: {e}")
            self._fan_mode = FAN_AUTO

    def UpdateHAStateToCurrentACState(self):
        """Update all HA states with comprehensive error handling"""
        try:
            self.UpdateHATargetTemperature()
            self.UpdateHAHvacMode()
            self.UpdateHAFanMode()
        except Exception as e:
            _LOGGER.error(f"Error updating HA state for {self._name}: {e}")
        # 设置安全默认值，避免设备变为不可用状态
            self._target_temperature = 26
            self._hvac_mode = HVACMode.OFF
            self._fan_mode = FAN_AUTO

    @callback
    def _async_update_current_temp(self, state):
        try:
            float(state.state)
            pass
        except ValueError:
            return
        """Update thermostat with latest state from sensor."""
        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), self._unit_of_measurement)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)
    @callback
    def _async_temp_sensor_changed(self, event: Event[EventStateChangedData]):
        entity_id = event.data["entity_id"]
        old_state = event.data["old_state"]
        new_state = event.data["new_state"]
        _LOGGER.info('temp_sensor state changed |' + str(entity_id) +
                     '|' + str(old_state) + '|' + str(new_state))
        if new_state is None:
            return
        self._async_update_current_temp(new_state)
        self.schedule_update_ha_state()
