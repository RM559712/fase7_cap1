from models.database.database import Database
from custom.aws import Aws
from custom.helper import Helper
import pprint

class F7C1Irrigation(Database):

    # Constantes referentes à origem da execução
    ORIGIN_MANUAL = 1
    ORIGIN_AUTOMATED = 2

    # Constantes referentes ao status de execução
    STATUS_EXECUTION_RUNNING = 1
    STATUS_EXECUTION_FINISHED = 2

    def __init__(self, object_database = None):

        super().__init__(object_database)

        self.table_name = Helper.convert_camel_to_snake_case(self.__class__.__name__)
        self.primary_key_column = 'IRG_ID'


    @staticmethod
    def get_params_to_active_data() -> dict:

        # Regras: Os registros são excluídos de forma lógica
        return {'str_column': 'IRG_STATUS', 'str_type_where': '=', 'value': Database.STATUS_ACTIVE}


    def validate_exists_data(self) -> bool:

        self.set_select([f'COUNT({self.primary_key_column}) as LENGTH'])
        self.set_where([self.get_params_to_active_data()])
        list_data = self.get_list()

        return False if len(list_data) == 0 or 'LENGTH' not in list_data[0] or list_data[0]['LENGTH'] == 0 else True


    def get_label_origin(self, irg_origin: int = 0) -> str:

        dict_labels = {}
        dict_labels[ self.ORIGIN_MANUAL ] = {'str_label': 'Inicialização manual'}
        dict_labels[ self.ORIGIN_AUTOMATED ] = {'str_label': 'Inicialização automatizada'}

        str_return = dict_labels[ irg_origin ]['str_label'] if irg_origin in dict_labels else 'N/I'
        return str_return


    def get_label_status_execution(self, irg_status_execution: int = 0) -> str:

        dict_labels = {}
        dict_labels[ self.STATUS_EXECUTION_RUNNING ] = {'str_label': 'Em execução'}
        dict_labels[ self.STATUS_EXECUTION_FINISHED ] = {'str_label': 'Finalizado'}

        str_return = dict_labels[ irg_status_execution ]['str_label'] if irg_status_execution in dict_labels else 'N/I'
        return str_return


    def get_active_execution_by_plantation(self, pln_id: int = 0) -> dict:

        dict_return = {'status': True, 'dict_data': {}}

        try:

            self.set_select(['IRG.*', 'PLN.PLN_NAME', 'CRP.CRP_NAME'])
            self.set_table('F7_C1_IRRIGATION IRG')
            self.set_join([
                {'str_type_join': 'INNER JOIN', 'str_table': 'F7_C1_PLANTATION PLN', 'str_where': 'PLN.PLN_ID = IRG.IRG_PLN_ID'},
                {'str_type_join': 'INNER JOIN', 'str_table': 'F7_C1_CROP CRP', 'str_where': 'CRP.CRP_ID = PLN.PLN_CRP_ID'}
            ])
            self.set_where([
                F7C1Irrigation.get_params_to_active_data(),
                {'str_column': 'PLN.PLN_ID', 'str_type_where': '=', 'value': pln_id},
                {'str_column': 'IRG.IRG_STATUS_EXECUTION', 'str_type_where': '=', 'value': self.STATUS_EXECUTION_RUNNING}
            ])
            dict_data = self.get_data().get_one()

            if type(dict_data) == type(None):
                raise Exception(f'Não foi possível concluir o processo pois a plantação informada não possui uma execução ativa.')
            
            dict_return['dict_data'] = dict_data

        except Exception as error:

            dict_return = {'status': False, 'message': error}

        return dict_return


    def get_finished_execution_by_plantation(self, pln_id: int = 0) -> dict:

        dict_return = {'status': True, 'list_data': []}

        try:

            self.set_select(['IRG.*', 'PLN.PLN_NAME', 'CRP.CRP_NAME'])
            self.set_table('F7_C1_IRRIGATION IRG')
            self.set_join([
                {'str_type_join': 'INNER JOIN', 'str_table': 'F7_C1_PLANTATION PLN', 'str_where': 'PLN.PLN_ID = IRG.IRG_PLN_ID'},
                {'str_type_join': 'INNER JOIN', 'str_table': 'F7_C1_CROP CRP', 'str_where': 'CRP.CRP_ID = PLN.PLN_CRP_ID'}
            ])
            self.set_where([
                F7C1Irrigation.get_params_to_active_data(),
                {'str_column': 'PLN.PLN_ID', 'str_type_where': '=', 'value': pln_id},
                {'str_column': 'IRG.IRG_STATUS_EXECUTION', 'str_type_where': '=', 'value': self.STATUS_EXECUTION_FINISHED}
            ])
            list_data = self.get_data().get_list()

            dict_return['list_data'] = list_data

        except Exception as error:

            dict_return = {'status': False, 'message': error}

        return dict_return


    def validate_exists_active_execution_by_plantation(self, pln_id: int = 0) -> bool:

        dict_active_irrigation = self.get_active_execution_by_plantation(pln_id)
        return dict_active_irrigation['status']


    def begin_execution_by_plantation(self, dict_params: dict = {}) -> dict:

        dict_return = {'status': True}

        try:

            if 'pln_id' not in dict_params or Helper.is_int(dict_params['pln_id']) == False:
                raise Exception(f'Não foi possível concluir o processo pois não foi definida nenhuma referência de plantação para iniciar uma irrigação.')

            if self.validate_exists_active_execution_by_plantation(dict_params['pln_id']) == True:
                raise Exception(f'Não foi possível concluir o processo pois a plantação informada já possui uma execução ativa.')

            dict_data = {}

            dict_data['IRG_PLN_ID'] = dict_params['pln_id']
            dict_data['IRG_ORIGIN'] = dict_params['irg_origin']

            self.insert(dict_data)

            dict_active_irrigation = self.get_active_execution_by_plantation(dict_params['pln_id'])
            if dict_active_irrigation['status'] == False:
                raise Exception(dict_active_irrigation['message'])

            object_aws = Aws()
            dict_send_message_by_begin_irrigation = object_aws.send_message_by_begin_irrigation(

                str_plantation_name = dict_active_irrigation['dict_data']['PLN_NAME'],
                str_ini_date = Helper.convert_date_to_pt_br(dict_active_irrigation['dict_data']['IRG_INI_DATE']),
                str_origin = self.get_label_origin(dict_active_irrigation['dict_data']['IRG_ORIGIN'])

            )

            if dict_send_message_by_begin_irrigation['status'] == False:
                raise Exception(dict_send_message_by_begin_irrigation['message'])

        except Exception as error:

            dict_return = {'status': False, 'message': error}

        return dict_return


    def finish_execution_by_plantation(self, dict_params: dict = {}) -> dict:

        dict_return = {'status': True}

        try:

            if 'pln_id' not in dict_params or Helper.is_int(dict_params['pln_id']) == False:
                raise Exception(f'Não foi possível concluir o processo pois não foi definida nenhuma referência de plantação para finalizar a irrigação.')

            if self.validate_exists_active_execution_by_plantation(dict_params['pln_id']) == False:
                raise Exception(f'Não foi possível concluir o processo pois a plantação informada não possui uma execução ativa.')

            dict_active_irrigation = self.get_active_execution_by_plantation(dict_params['pln_id'])
            if dict_active_irrigation['status'] == False:
                    raise Exception(dict_active_irrigation['message'])

            irg_water = dict_params['irg_water'] if 'irg_water' in dict_params and Helper.is_float(dict_params['irg_water']) == True else 0.00

            dict_active_irrigation['dict_data']['IRG_WATER'] = irg_water
            dict_active_irrigation['dict_data']['IRG_END_DATE'] = f"TO_TIMESTAMP('{Helper.get_current_datetime_to_oracle()}', 'DD/MM/YYYY HH24:MI:SS.FF6')"
            dict_active_irrigation['dict_data']['IRG_STATUS_EXECUTION'] = self.STATUS_EXECUTION_FINISHED

            self.update(dict_active_irrigation['dict_data'])

            object_aws = Aws()
            dict_send_message_by_end_irrigation = object_aws.send_message_by_end_irrigation(

                str_plantation_name = dict_active_irrigation['dict_data']['PLN_NAME'],
                str_end_date = Helper.convert_date_to_pt_br(Helper.get_current_datetime()),
                float_water = float(dict_active_irrigation['dict_data']['IRG_WATER'])

            )

            if dict_send_message_by_end_irrigation['status'] == False:
                raise Exception(dict_send_message_by_end_irrigation['message'])

        except Exception as error:

            dict_return = {'status': False, 'message': error}

        return dict_return


